"""Retrieval over the contract and BOQ corpus.

The platform's knowledge surface: ingest a document's text, chunk it, and
answer a query with the passages that actually match. Ranking lives in
``app.retrieval`` and the grounded answer in ``app.llm``; both run entirely on
the platform's own database -- no network, no external vector service.

Ingest: POST /v1/rag/ingest  {"text" | "content" | "paragraph": "..."}
Query:  POST /v1/rag/query   {"q" | "query": "..."}
        GET  /v1/rag/query?q=...
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import llm, retrieval, security, store

ROUTER = APIRouter(prefix="/v1/rag", tags=["retrieval"])


def _ingest_text(payload: Dict[str, Any]) -> str:
    for key in ("text", "content", "paragraph", "document"):
        value = (payload or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _query_text(payload: Dict[str, Any], fallback: str = "") -> str:
    for key in ("q", "query", "question"):
        value = (payload or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(fallback or "").strip()


@ROUTER.post("/ingest")
def rag_ingest(request: Request, payload: Optional[Dict[str, Any]] = None):
    principal = security.principal_from_request(request)
    body = dict(payload or {})
    text = _ingest_text(body)
    if not text:
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": "document text is required (text, content or paragraph)",
                "rejected_field": "text",
                "rejection_reason": "missing_required",
            },
        )
    source = str(body.get("source") or body.get("title") or "uploaded-document")
    chunks = retrieval.chunk_text(text)
    document = store.save(
        "rag_documents",
        {
            "source": source,
            "title": str(body.get("title") or source),
            "text": text,
            "authority": str(body.get("authority") or "layer 2 documents"),
            "chunk_count": len(chunks),
        },
        tenant_id=principal.tenant_id,
    )
    for ordinal, chunk in enumerate(chunks):
        store.save(
            "rag_chunks",
            {"document_id": document.get("id"), "ordinal": ordinal, "text": chunk},
            tenant_id=principal.tenant_id,
        )
    return {
        "ok": True,
        "document_id": document.get("id"),
        "source": source,
        "chunks": len(chunks),
    }


@ROUTER.post("/query")
def rag_query(request: Request, payload: Optional[Dict[str, Any]] = None):
    principal = security.principal_from_request(request)
    question = _query_text(dict(payload or {}))
    if not question:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "q or query is required", "rejected_field": "q", "rejection_reason": "missing_required"},
        )
    return llm.answer(question, principal.tenant_id)


@ROUTER.get("/query")
def rag_query_get(request: Request, q: str = "", query: str = ""):
    principal = security.principal_from_request(request)
    question = q.strip() or query.strip()
    if not question:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "q or query is required", "rejected_field": "q", "rejection_reason": "missing_required"},
        )
    return llm.answer(question, principal.tenant_id)
