"""The retrieval surface: ingest sources, query them, see the authority label.

The corpus is empty until the customer supplies sources -- this module ships
the ingest and query surface and never seeds documents. Ingest takes the
document text in any of ``text`` / ``content`` / ``paragraph``; query accepts a
GET query string or a POST body and answers with the retrieved content, its
citations and the layer it came from, or an empty result when nothing matches.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app import retrieval, security

RAG = APIRouter(prefix="/v1/rag", tags=["retrieval"])

TEXT_FIELDS = ("text", "content", "paragraph")


def _document_text(payload: Dict[str, Any]) -> str:
    for field in TEXT_FIELDS:
        value = (payload or {}).get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@RAG.post("/ingest")
def ingest(payload: Dict[str, Any], request: Request):
    principal = security.principal_from_request(request)
    text = _document_text(payload or {})
    if not text:
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "rejected_field": "text",
                "rejection_reason": "missing_required",
                "error": "ingest needs the document text in text, content or paragraph",
            },
            headers={"X-Rejected-Field": '"text"', "X-Rejection-Reason": "missing_required"},
        )
    document = retrieval.ingest(
        text,
        principal.tenant_id,
        source=str((payload or {}).get("source") or ""),
        title=str((payload or {}).get("title") or ""),
        authority=str((payload or {}).get("authority") or retrieval.DEFAULT_AUTHORITY),
    )
    return {
        "ok": True,
        "document": document,
        "chunks": document.get("chunk_count"),
        "tenant_id": principal.tenant_id,
    }


def _answer(query: str, principal) -> Dict[str, Any]:
    if not str(query or "").strip():
        return {
            "ok": False,
            "error": "a query is required",
            "rejected_field": "q",
            "rejection_reason": "missing_required",
            "hits": [],
            "citations": [],
        }
    return retrieval.answer(str(query), principal.tenant_id)


@RAG.get("/query")
def query_get(request: Request, q: Optional[str] = Query(default=None)):
    principal = security.principal_from_request(request)
    return _answer(q or "", principal)


@RAG.post("/query")
def query_post(request: Request, payload: Optional[Dict[str, Any]] = None):
    principal = security.principal_from_request(request)
    body = dict(payload or {})
    query = str(body.get("q") or body.get("query") or body.get("question") or "")
    return _answer(query, principal)


@RAG.get("/documents")
def documents(request: Request):
    principal = security.principal_from_request(request)
    rows = retrieval.documents(principal.tenant_id)
    return {"ok": True, "items": rows, "total": len(rows)}
