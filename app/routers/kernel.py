"""Kernel console routes: what the platform is, what it can do, and how it
was built. Every one requires the platform principal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app import authority, jobs, models, retrieval, store
from app.routers.capabilities import current_tenant

router = APIRouter(tags=["kernel"])

ROOT = Path(__file__).resolve().parents[2]


def _lock() -> Dict[str, Any]:
    for path in (ROOT / "blocks.lock.json", ROOT.parent / "product" / "blocks.lock.json"):
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return {}


@router.get("/v1/jobs")
async def list_jobs(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    return {"ok": True, "jobs": jobs.KERNEL_JOBS}


@router.get("/v1/catalog")
async def catalog(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "capabilities": [
            {"id": row["id"], "title": row["title"], "blocks": row["blocks"]}
            for row in jobs.CAPABILITIES
        ],
    }


@router.get("/v1/inventory")
async def inventory(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    lock = _lock()
    return {
        "ok": True,
        "kernel": "CLONER",
        "lock": lock,
        "blocks": sorted(
            {block for row in jobs.CAPABILITIES for block in row["blocks"]}
        ),
    }


@router.get("/v1/capabilities")
async def capabilities(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    items = []
    for row in jobs.CAPABILITIES:
        model = models.model_for(row["id"])
        items.append(
            {
                "id": row["id"],
                "entity": row["entity"],
                "title": row["title"],
                "summary": row["summary"],
                "sources": row["sources"],
                "blocks": row["blocks"],
                "fields": jobs.fields_for(row["id"]),
                "required": model.required_fields() if model else [],
            }
        )
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "authority": authority.ladder(),
    }


@router.get("/v1/retrieval")
async def retrieval_query(q: str = "", limit: int = 5, tenant=Depends(current_tenant)) -> Dict[str, Any]:
    """Search the uploaded contract and BOQ: the only corpus this product has."""
    hits = retrieval.search(q, limit=limit)
    return {"ok": True, "query": q, "items": hits, "total": len(hits)}


@router.get("/v1/gates")
async def gates(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "checks": [
            "no_token_401",
            "missing_field_422",
            "enum_422",
            "cross_tenant_404",
            "one_record_round_trip",
            "migration_no_create_all",
        ],
    }


@router.get("/v1/provenance")
async def provenance(tenant=Depends(current_tenant)) -> Dict[str, Any]:
    path = ROOT / "docs" / "provenance" / "provenance.json"
    data: Dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "provenance": data,
        "capabilities": [
            {"id": row["id"], "entity": row["entity"], "records": len(store.list_all(row["entity"], tenant.tenant_id))}
            for row in jobs.CAPABILITIES
        ],
    }
