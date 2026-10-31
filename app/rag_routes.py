"""Document retrieval surface: ingest and query over the tenant corpus."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import llm, retrieval
from app.authority import authority
from app.tenancy import Unauthorized, current_tenant, require_principal, reset_current_tenant, set_current_tenant

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
    token = set_current_tenant(principal.tenant_id)
    try:
        saved = retrieval.ingest(
            text,
            source=str(body.get("source") or "upload"),
            document_name=str(body.get("document_name") or body.get("title") or ""),
            document_type=str(body.get("document_type") or "bom"),
            tenant_id=principal.tenant_id,
        )
    finally:
        reset_current_tenant(token)
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
    if not question.strip():
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_required",
                                                      "rejected_field": "q",
                                                      "rejection_reason": "missing_required"})
    return JSONResponse(status_code=200, content=_query(principal.tenant_id, question, top_k))


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
    if not question.strip():
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_required",
                                                      "rejected_field": "q",
                                                      "rejection_reason": "missing_required"})
    return JSONResponse(status_code=200, content=_query(principal.tenant_id, question, top_k))
