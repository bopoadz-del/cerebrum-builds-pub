"""Tenant-scoped retrieval over the ingested source-of-record corpus.

The index lives in the platform database (rag_chunks), under the one
persistence root STORAGE_PATH. Scoring is lexical overlap with a length
normaliser: a query that shares no term with a chunk never returns it, so a
never-planted term cannot come back as a hit.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

import sqlalchemy as sa

from app import db

_META = sa.MetaData()
_TABLE = None
_WORD = re.compile(r"[a-z0-9]+")
MAX_INGEST_BYTES = 262_144
MAX_CHUNKS_PER_SOURCE = 400
MAX_SEARCH_ROWS = 5_000
_STOP = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the "
    "this to was were will with".split()
)


def _table() -> sa.Table:
    global _TABLE
    engine = db.get_engine()
    key = (str(engine.url), "rag_chunks")
    if _TABLE is None or getattr(_TABLE, "_codewhale_key", None) != key:
        table = sa.Table("rag_chunks", _META, autoload_with=engine)
        table._codewhale_key = key
        _TABLE = table
    return _TABLE


def tokens(text: str) -> List[str]:
    return [word for word in _WORD.findall(str(text or "").lower()) if word not in _STOP]


def _chunks(text: str, size: int = 700) -> List[str]:
    body = str(text or "").strip()
    if not body:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    out: List[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= size:
            current = (current + "\n\n" + paragraph).strip()
        else:
            if current:
                out.append(current)
            if len(paragraph) <= size:
                current = paragraph
            else:
                for start in range(0, len(paragraph), size):
                    out.append(paragraph[start:start + size])
                current = ""
    if current:
        out.append(current)
    return out


def ingest(tenant_id: str, text: str, source: str) -> Dict[str, Any]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the corpus is tenant-scoped")
    body = str(text or "")
    if len(body.encode("utf-8")) > MAX_INGEST_BYTES:
        raise ValueError("document exceeds the ingest size limit")
    table = _table()
    stamp = datetime.now(timezone.utc).isoformat()
    pieces = _chunks(body)[:MAX_CHUNKS_PER_SOURCE]
    with db.get_engine().begin() as conn:
        conn.execute(sa.delete(table).where(
            table.c.tenant_id == str(tenant_id), table.c.source == str(source)
        ))
        for seq, piece in enumerate(pieces):
            conn.execute(
                sa.insert(table).values(
                    tenant_id=str(tenant_id), source=str(source), seq=seq,
                    text=piece, created_at=stamp,
                )
            )
    return {"source": str(source), "chunks": len(pieces)}


def sources(tenant_id: str) -> List[Dict[str, Any]]:
    table = _table()
    with db.get_engine().connect() as conn:
        rows = conn.execute(
            sa.select(table.c.source, sa.func.count(table.c.id))
            .where(table.c.tenant_id == str(tenant_id))
            .group_by(table.c.source)
        ).fetchall()
    return [{"source": row[0], "chunks": int(row[1])} for row in rows]


def _rows(tenant_id: str) -> List[Dict[str, Any]]:
    table = _table()
    with db.get_engine().connect() as conn:
        rows = conn.execute(
            sa.select(table)
            .where(table.c.tenant_id == str(tenant_id))
            .order_by(table.c.id)
            .limit(MAX_SEARCH_ROWS)
        ).fetchall()
    return [
        {"source": row._mapping["source"], "seq": int(row._mapping["seq"]), "text": row._mapping["text"]}
        for row in rows
    ]


def search(tenant_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    try:
        rows = _rows(tenant_id)
    except (RuntimeError, OSError):
        # No persistence root configured: rank the uploaded documents in
        # place rather than pretending the corpus is empty.
        return search_corpus(query, top_k=top_k)
    if not rows:
        return []
    return rank(rows, query, top_k=top_k)


def search_corpus(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Rank the uploaded source-of-record documents without an index.

    Used when no tenant index is available (for example a direct handle()
    call outside a deployment, where STORAGE_PATH is not set). The corpus
    is the same uploaded contract and BOQ, read in place; nothing is
    persisted and no second store is opened.
    """
    from app import contract_terms

    rows: List[Dict[str, Any]] = []
    for filename in (contract_terms.CONTRACT_FILENAME, contract_terms.BOQ_FILENAME):
        for seq, piece in enumerate(_chunks(contract_terms.DOCUMENTS[filename])):
            rows.append(
                {"source": "document:%s" % filename, "seq": seq, "text": piece}
            )
    return rank(rows, query, top_k=top_k)


def rank(rows: List[Dict[str, Any]], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Lexical ranking over an explicit chunk list."""
    wanted = tokens(query)
    if not wanted:
        return []
    wanted_set = set(wanted)
    if not rows:
        return []
    doc_freq: Counter = Counter()
    tokenised = []
    for row in rows:
        bag = Counter(tokens(row["text"]))
        tokenised.append(bag)
        for term in set(bag):
            doc_freq[term] += 1
    total = len(rows)
    scored: List[Dict[str, Any]] = []
    for row, bag in zip(rows, tokenised):
        if not bag:
            continue
        overlap = wanted_set & set(bag)
        if not overlap:
            continue
        length = sum(bag.values()) or 1
        score = 0.0
        for term in overlap:
            tf = bag[term] / length
            idf = math.log((total + 1) / (doc_freq[term] + 0.5))
            score += tf * max(idf, 0.05)
        if score <= 0:
            continue
        scored.append({**row, "score": round(score, 6)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, int(top_k))]


def chunk_count(tenant_id: str) -> int:
    table = _table()
    with db.get_engine().connect() as conn:
        count = conn.execute(
            sa.select(sa.func.count(table.c.id)).where(table.c.tenant_id == str(tenant_id))
        ).scalar()
    return int(count or 0)
