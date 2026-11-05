"""Tenant-scoped document ingest and query.

The corpus is empty until the customer supplies sources: this surface stores
what they send and finds it again through the retrieval path. Both routes
resolve the tenant from the authenticated principal, never from the body.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import retrieval
from app.authority import authority_label
from app.security import authenticate

router = APIRouter(prefix="/v1", tags=["retrieval"])


def _rejection(exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    body = {"ok": False, "error": "validation_error", **detail}
    headers = {
        "X-Rejected-Field": str(detail.get("rejected_field", "")),
        "X-Rejection-Reason": str(detail.get("rejection_reason", "")),
    }
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

_TEXT_FIELDS = ("text", "content", "paragraph")


def _document_text(payload: Dict[str, Any]) -> str:
    for field in _TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return ""


@router.post("/rag/ingest")
async def ingest(request: Request) -> Any:
    principal = authenticate(request.headers)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail={"error": "payload must be an object"})
    text = _document_text(payload)
    if not text:
        return _rejection(
            HTTPException(
                status_code=422,
                detail={
                    "error": "validation_error",
                    "rejected_field": "text",
                    "rejection_reason": "missing_required",
                    "message": "one of text, content or paragraph is required",
                },
            )
        )
    stored = await run_in_threadpool(
        retrieval.ingest,
        principal.tenant_id,
        text,
        str(payload.get("source") or payload.get("title") or ""),
        payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "id": stored.get("id"),
            "source": stored.get("source"),
            "characters": stored.get("characters"),
            "authority": authority_label(2),
        },
    )


@router.get("/rag/query")
async def query_get(request: Request) -> Any:
    principal = authenticate(request.headers)
    text = str(request.query_params.get("q") or request.query_params.get("query") or "").strip()
    return await run_in_threadpool(_answer, principal.tenant_id, text)


@router.post("/rag/query")
async def query_post(request: Request) -> Any:
    principal = authenticate(request.headers)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    text = str(payload.get("q") or payload.get("query") or payload.get("text") or "").strip()
    return await run_in_threadpool(_answer, principal.tenant_id, text)


def _answer(tenant_id: str, text: str) -> JSONResponse:
    if not text:
        return _rejection(
            HTTPException(
                status_code=422,
                detail={
                    "error": "validation_error",
                    "rejected_field": "q",
                    "rejection_reason": "missing_required",
                    "message": "a query term is required",
                },
            )
        )
    body = retrieval.answer(tenant_id, text)
    return JSONResponse(status_code=200, content=body)
