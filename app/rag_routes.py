"""Retrieval surface: ingest project text and query it back.

The contract and BOQ capabilities bind the Store's vector-search read, so the
platform ships a tenant-scoped retrieval surface over its own database. It is
a real term-overlap index, not a vector store copy: ingested chunks are
persisted, and a query scores the caller's tenant's chunks only.

Routes (mounted under /v1):
  POST /v1/rag/ingest   body: text | content | paragraph
  GET  /v1/rag/query     ?q=...
  POST /v1/rag/query     body: q | query | text

Scope READS: the caller's tenant's chunks in the configured database.
Scope WRITES: chunks the caller ingested, under the caller's tenant.
Scope NEVER: no network, no cross-tenant read, no seeded corpus.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import db as _db
from app.auth import require_platform_token

router = APIRouter()

_TABLE = sa.table(
    "rag_chunks",
    sa.column("id"),
    sa.column("tenant_id"),
    sa.column("document_id"),
    sa.column("chunk"),
    sa.column("tokens"),
    sa.column("created_at"),
)
_SQLITE = _sqlite_dialect.dialect(paramstyle="qmark")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "by", "with", "as", "at", "from", "that",
    "this", "it", "its", "which", "what", "when", "how",
}

AUTHORITY = {
    "layer": 2,
    "name": "documents",
    "source": "app/rag_routes.py",
    "precedence": "precedence.v1",
}


def _execute(conn: Any, statement: Any) -> Any:
    if _db.is_postgres():
        return conn.execute(statement)
    compiled = statement.compile(dialect=_SQLITE)
    params = [compiled.params[name] for name in (compiled.positiontup or ())]
    return conn.execute(str(compiled), params)


def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return [word for word in words if len(word) > 1 and word not in _STOPWORDS]


def _chunks(text: str, size: int = 1200) -> List[str]:
    body = str(text or "").strip()
    if not body:
        return []
    if len(body) <= size:
        return [body]
    out: List[str] = []
    start = 0
    while start < len(body):
        out.append(body[start:start + size])
        start += size
    return out


def _bad(message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content={"ok": False, "error": message})


@router.post("/rag/ingest")
async def ingest(request: Request) -> Any:
    tenant = require_platform_token(request)
    try:
        body = await request.json()
    except Exception:
        return _bad("body must be a JSON object")
    if not isinstance(body, dict):
        return _bad("body must be a JSON object")
    text = ""
    for field in ("text", "content", "paragraph"):
        value = body.get(field)
        if isinstance(value, str) and value.strip():
            text = value
            break
    if not text:
        return _bad("one of text, content or paragraph is required")
    document_id = str(body.get("document_id") or body.get("source") or "inline")
    inserted = 0
    conn = _db.connect()
    try:
        for index, chunk in enumerate(_chunks(text)):
            statement = sa.insert(_TABLE).values(
                tenant_id=tenant.tenant_id,
                document_id=document_id,
                chunk=chunk,
                tokens=" ".join(_tokens(chunk)),
                created_at="%d" % index,
            )
            _execute(conn, statement)
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "ingested": inserted,
        "document_id": document_id,
        "authority": dict(AUTHORITY),
    }


def _query_text(params: Dict[str, Any], body: Dict[str, Any]) -> str:
    for source in (body, params):
        for field in ("q", "query", "text"):
            value = source.get(field)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _search(tenant_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    wanted = set(_tokens(query))
    if not wanted:
        return []
    statement = sa.select(_TABLE).where(_TABLE.c.tenant_id == tenant_id)
    conn = _db.connect()
    try:
        rows = _execute(conn, statement).fetchall()
    finally:
        conn.close()
    scored: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        have = set(str(item.get("tokens") or "").split())
        overlap = wanted & have
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


@router.get("/rag/query")
def query_get(request: Request) -> Any:
    tenant = require_platform_token(request)
    text = _query_text(dict(request.query_params), {})
    if not text:
        return _bad("q or query is required")
    hits = _search(tenant.tenant_id, text)
    return {
        "ok": True,
        "results": hits,
        "total": len(hits),
        "authority": dict(AUTHORITY),
    }


@router.post("/rag/query")
async def query_post(request: Request) -> Any:
    tenant = require_platform_token(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = _query_text({}, body if isinstance(body, dict) else {})
    if not text:
        return _bad("q or query is required")
    hits = _search(tenant.tenant_id, text)
    return {
        "ok": True,
        "results": hits,
        "total": len(hits),
        "authority": dict(AUTHORITY),
    }
