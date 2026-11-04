"""Retrieval surface: ingest customer sources, query them with citations."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app import llm, retrieval
from app.security import require_principal
from app.tenancy import Principal, tenant_of

router = APIRouter()


def _top_k(raw: Any) -> int:
    if raw in (None, ""):
        return 5
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="top_k must be an integer") from exc
    return max(1, min(value, 50))


MAX_QUERY_CHARS = 2000


def _query_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if len(text) > MAX_QUERY_CHARS:
        raise HTTPException(status_code=422, detail="query is longer than 2000 characters")
    return text


def _body_text(body: Dict[str, Any]) -> str:
    for key in ("text", "content", "paragraph"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


@router.get("/v1/rag/ingest")
def ingest_method_guard(principal: Principal = Depends(require_principal)) -> JSONResponse:
    """Ingest is a POST: answer the wrong verb as such, not as an unknown path.

    Without this declaration the dynamic ``/v1/{capability_id}/{record_id}``
    route answers GET here with 404 (no capability named "rag"), which reads
    as a missing route to a caller that only probed the URL.
    """
    return JSONResponse(
        status_code=405,
        content={"ok": False, "error": "ingest takes POST with text, content or paragraph"},
        headers={"Allow": "POST"},
    )


@router.post("/v1/rag/ingest")
def ingest(body: Dict[str, Any] = Body(default_factory=dict),
           principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    text = _body_text(body)
    if not text:
        raise HTTPException(status_code=422, detail="text, content or paragraph is required")
    if len(text.encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=413, detail="source is larger than the 2 MB ingest limit")
    source = str(body.get("source") or body.get("filename") or "upload")
    try:
        result = retrieval.ingest(text, source, tenant_of(principal))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "source": result["source"], "chunks": result["chunks"], "ids": result["ids"]}


def _answer(query: str, tenant_id: str, top_k: int) -> Dict[str, Any]:
    chunks = retrieval.search(query, tenant_id, top_k)
    answered = llm.answer(query, chunks)
    return {
        "ok": True,
        "query": query,
        "results": chunks,
        "answer": answered["answer"],
        "claims": answered["claims"],
        "citations": answered["citations"],
        "refused": answered["refused"],
        "authority": answered["authority"],
    }


@router.post("/v1/rag/query")
def query_post(body: Dict[str, Any] = Body(default_factory=dict),
               principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    query = _query_text(body.get("query") or body.get("q") or body.get("question"))
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    return _answer(query, tenant_of(principal), _top_k(body.get("top_k")))


@router.get("/v1/rag/query")
def query_get(q: str = Query(default=""), principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    query = _query_text(q)
    if not query:
        raise HTTPException(status_code=422, detail="q is required")
    return _answer(query, tenant_of(principal), 5)


@router.get("/v1/rag/status")
def rag_status(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(retrieval.status(tenant_of(principal)), ok=True)
