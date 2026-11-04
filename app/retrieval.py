"""Document retrieval over the tenant's ingested corpus.

Chunks live in the single persistence root (``retrieval_chunk`` table) and are
scored by term overlap -- no external vector service, no network.  A query
that matches nothing returns nothing: the surface is empty until the customer
supplies sources, and it never answers its own request back.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

from app import store

ENTITY = "retrieval_chunk"
_WORD = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")


def _terms(text: str) -> set:
    return set(_WORD.findall(str(text or "").lower()))


def chunk_text(text: str, size: int = 900) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", str(text or "")) if p.strip()]
    chunks: List[str] = []
    for paragraph in paragraphs:
        while len(paragraph) > size:
            cut = paragraph.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if paragraph:
            chunks.append(paragraph)
    return chunks


def ingest(text: str, source: str, tenant_id: str) -> Dict[str, Any]:
    body = str(text or "").strip()
    if not body:
        raise ValueError("text is required: there is nothing to ingest")
    chunks = chunk_text(body)
    stored = []
    for index, chunk in enumerate(chunks):
        digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        stored.append(
            store.save(
                ENTITY,
                {
                    "source": str(source or "upload"),
                    "chunk_index": index,
                    "text": chunk,
                    "digest": digest,
                },
                tenant_id,
            )
        )
    return {
        "source": str(source or "upload"),
        "chunks": len(stored),
        "ids": [row["id"] for row in stored],
    }


def search(query: str, tenant_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    wanted = _terms(query)
    if not wanted:
        return []
    scored = []
    for row in store.list_all(ENTITY, tenant_id):
        haystack = _terms(row.get("text"))
        overlap = len(wanted & haystack)
        if overlap <= 0:
            continue
        score = overlap / float(len(wanted))
        scored.append({
            "id": row.get("id"),
            "source": row.get("source"),
            "text": row.get("text"),
            "score": round(score, 4),
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, int(top_k))]


def status(tenant_id: str) -> Dict[str, Any]:
    rows = store.list_all(ENTITY, tenant_id)
    return {"chunks": len(rows), "sources": sorted({str(r.get("source") or "") for r in rows})}
