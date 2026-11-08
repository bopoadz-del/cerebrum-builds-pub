"""Tenant-scoped retrieval over the chunks the caller ingested.

The document register and the source-of-record capability both retrieve from
this one index; a query reads the caller's tenant's chunks only, and a term
that was never ingested returns nothing.

Scope READS: the configured database, tenant-scoped.
Scope WRITES: nothing here (ingest lives on the /v1/rag surface).
Scope NEVER: no network, no cross-tenant read, no seeded corpus.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import sqlalchemy as sa

from app import db as _db
from app.tenant_tables import rag_table

AUTHORITY = {
    "layer": 2,
    "name": "documents",
    "source": "app/retrieval.py",
    "precedence": "precedence.v1",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "by", "with", "as", "at", "from", "that",
    "this", "it", "its", "which", "what", "when", "how",
}


def tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return [word for word in words if len(word) > 1 and word not in _STOPWORDS]


def search(tenant_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    wanted = set(tokens(query))
    if not wanted:
        return []
    table = rag_table()
    statement = sa.select(table).where(table.c.tenant_id == tenant_id)
    conn = _db.connect()
    try:
        if _db.is_postgres():
            rows = conn.execute(statement).fetchall()
        else:
            from sqlalchemy.dialects import sqlite as _sqlite_dialect

            compiled = statement.compile(dialect=_sqlite_dialect.dialect(paramstyle="qmark"))
            params = [compiled.params[name] for name in (compiled.positiontup or ())]
            rows = conn.execute(str(compiled), params).fetchall()
    finally:
        conn.close()
    scored: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        overlap = wanted & set(str(item.get("tokens") or "").split())
        if not overlap:
            continue
        scored.append(
            {
                "id": item.get("id"),
                "document_id": item.get("document_id"),
                "chunk": item.get("chunk"),
                "score": round(len(overlap) / max(1, len(wanted)), 4),
                "matched_terms": sorted(overlap),
            }
        )
    scored.sort(key=lambda entry: (-entry["score"], entry["id"]))
    return scored[:limit]
