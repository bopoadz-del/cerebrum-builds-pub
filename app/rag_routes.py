"""Hotel property notes ingest/query HTTP. Quoted paths required by PHASE 2."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import require_operator
from app.block_inputs import record_mutation_audit
from app.store import storage_root

router = APIRouter()

HOTEL_INDEX = "hotel_property_notes_v1"


class RagIngestBody(BaseModel):
    text: str = Field(..., min_length=1)
    doc_id: str = Field("sample", min_length=1)
    title: str = Field("sample", min_length=1)
    layer: int = Field(1, ge=1, le=2)
    property_id: Optional[str] = None


def _rag_dir() -> Path:
    path = storage_root() / "rag"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path() -> Path:
    return _rag_dir() / f"{HOTEL_INDEX}.jsonl"


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t]


def _score(query: str, text: str) -> float:
    q = set(_tokens(query))
    d = _tokens(text)
    if not q or not d:
        return 0.0
    overlap = len(q.intersection(d))
    return overlap / math.sqrt(len(q) * max(len(d), 1))


def _read_index() -> List[Dict[str, Any]]:
    path = _index_path()
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


@router.post("/v1/rag/ingest")
def rag_ingest(body: RagIngestBody, request: Request) -> Dict[str, Any]:
    principal = require_operator(request)
    record = {
        "doc_id": body.doc_id,
        "title": body.title,
        "text": body.text,
        "layer": body.layer,
        "property_id": body.property_id,
        "index": HOTEL_INDEX,
        "retrieval": "lexical_jsonl",
        "actor": principal.subject,
        "actor_role": principal.role,
    }
    path = _index_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    record_mutation_audit(
        principal,
        action="rag_ingest",
        resource=body.doc_id,
        details={
            "status": "open",
            "capability": "rag_ingest",
            "category": "hospitality",
            "layer": body.layer,
            "retrieval": "lexical_jsonl",
        },
    )
    return {
        "ok": True,
        "ingested": True,
        "doc_id": body.doc_id,
        "layer": body.layer,
        "retrieval": "lexical_jsonl",
        "actor": principal.subject,
        "actor_role": principal.role,
    }


@router.post("/v1/steward/rag/ingest")
def steward_rag_ingest(body: RagIngestBody, request: Request) -> Dict[str, Any]:
    return rag_ingest(body, request)


@router.get("/v1/rag/query")
def rag_query(
    q: str = Query(..., min_length=1),
    layer: Optional[int] = Query(None, ge=1, le=2),
    top_k: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    hits = []
    for row in _read_index():
        if layer is not None and row.get("layer") != layer:
            continue
        score = _score(q, f"{row.get('title', '')} {row.get('text', '')}")
        if score <= 0:
            continue
        hits.append({**row, "score": round(score, 6)})
    hits.sort(key=lambda item: item["score"], reverse=True)
    return {
        "ok": True,
        "query": q,
        "hits": hits[:top_k],
        "hit_count": min(len(hits), top_k),
        "retrieval": "lexical_jsonl",
    }


@router.post("/v1/rag/query")
def rag_query_post(body: Dict[str, Any]) -> Dict[str, Any]:
    q = str(body.get("q") or body.get("query") or "")
    if not q:
        raise HTTPException(status_code=422, detail="q required")
    layer = body.get("layer")
    top_k = int(body.get("top_k") or 5)
    return rag_query(q=q, layer=layer, top_k=top_k)


@router.get("/v1/steward/rag/query")
def steward_rag_query(
    q: str = Query(..., min_length=1),
    layer: Optional[int] = Query(None, ge=1, le=2),
    top_k: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    return rag_query(q=q, layer=layer, top_k=top_k)


@router.post("/v1/steward/rag/query")
def steward_rag_query_post(body: Dict[str, Any]) -> Dict[str, Any]:
    return rag_query_post(body)
