"""Document retrieval surface: ingest and query over the tenant corpus."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import llm, retrieval, security
from app.authority import authority
from app.tenancy import Unauthorized, require_principal, reset_current_tenant, set_current_tenant

router = APIRouter()

TEXT_FIELDS = ("text", "content", "paragraph")


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})


def _text_of(body: Dict[str, Any]) -> str:
    for name in TEXT_FIELDS:
        value = body.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return ""


@router.post("/v1/rag/ingest", operation_id="rag_ingest")
async def ingest(request: Request):
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    raw = await request.body()
    if security.body_too_large(raw):
        return JSONResponse(status_code=413, content={"ok": False, "error": "body_too_large"})
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    text = _text_of(body)
    if not text:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "missing_required", "rejected_field": "text",
                     "rejection_reason": "missing_required"},
            headers={"X-Rejected-Field": json.dumps("text"), "X-Rejection-Reason": "missing_required"},
        )
    saved = await run_in_threadpool(
        retrieval.ingest,
        text,
        str(body.get("source") or "upload"),
        str(body.get("document_name") or body.get("title") or ""),
        str(body.get("document_type") or "bom"),
        principal.tenant_id,
        str(body.get("plant") or ""),
    )
    return JSONResponse(
        status_code=200,
        content={"ok": True, "id": saved.get("id"), "record": saved, "stored": saved,
                 "characters": len(text)},
    )


def _query(tenant_id: str, question: str, top_k: int) -> Dict[str, Any]:
    token = set_current_tenant(tenant_id)
    try:
        hits = retrieval.search(question, top_k=top_k, tenant_id=tenant_id)
    finally:
        reset_current_tenant(token)
    synthesis = llm.synthesize(question, hits)
    return {
        "ok": True,
        "answer": synthesis["answer"],
        "confidence": synthesis["confidence"],
        "sources": retrieval.citations(hits),
        "authority": authority(2, source="tenant_corpus"),
    }


@router.get("/v1/rag/query", operation_id="rag_query_get")
async def query_get(request: Request):
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    params = request.query_params
    question = str(params.get("q") or params.get("query") or "")
    try:
        top_k = int(params.get("top_k") or 5)
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(20, top_k))
    if not question.strip():
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_required",
                                                      "rejected_field": "q",
                                                      "rejection_reason": "missing_required"})
    body = await run_in_threadpool(_query, principal.tenant_id, question, top_k)
    return JSONResponse(status_code=200, content=body)


@router.post("/v1/rag/query", operation_id="rag_query_post")
async def query_post(request: Request):
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    question = str(body.get("q") or body.get("query") or body.get("question") or "")
    try:
        top_k = int(body.get("top_k") or 5)
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(20, top_k))
    if not question.strip():
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_required",
                                                      "rejected_field": "q",
                                                      "rejection_reason": "missing_required"})
    body = await run_in_threadpool(_query, principal.tenant_id, question, top_k)
    return JSONResponse(status_code=200, content=body)
