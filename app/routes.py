"""Kernel roster and product metadata endpoints (all authenticated)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app import jobs, work_queue
from app.authority import authority_label, ladder
from app.cerebrum_product_kernel.contract.models import ActionContext, ActionStatus
from app.cerebrum_product_kernel.contract.runtime import execute_action
from app.jobs import CAPABILITIES
from app.kernel_bridge import spec_for
from app.security import require_principal
from app.tenancy import Principal

router = APIRouter(prefix="/v1", tags=["kernel"])

JOBS = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store and bind the exact blocks the capability roster names.",
        "http_routes": ["/v1/catalog", "/v1/capabilities"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Stock every locked block at its pinned vendor path and seal the lockfile.",
        "http_routes": ["/v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author the capability handlers, routes and models that run on the stocked blocks.",
        "http_routes": ["/v1/capabilities"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the product gates over the booted platform and record every failure by capability.",
        "http_routes": ["/v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Register the product provenance and publish the pilot candidate when every gate is green.",
        "http_routes": ["/v1/provenance"],
        "agent": "store_manager",
    },
]

ROUTE_ENTITIES = {item["id"]: item["entity"] for item in CAPABILITIES}


@router.get("/jobs")
def jobs_roster(principal: Principal = Depends(require_principal)):
    return {"ok": True, "jobs": JOBS, "authority": authority_label("procedures", detail="kernel roster")}


@router.get("/catalog")
def catalog(principal: Principal = Depends(require_principal)):
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "capabilities": [
            {"id": item["id"], "title": item["title"], "blocks": item["blocks"]}
            for item in CAPABILITIES
        ],
        "authority": authority_label("procedures", detail="bound block catalogue"),
    }


@router.get("/inventory")
def inventory(principal: Principal = Depends(require_principal)):
    from app.dispatch import BLOCK_DEFAULT_ACTIONS, LOCKED_BLOCKS

    return {
        "ok": True,
        "kernel": "CLONER",
        "lock": {block: str(path.relative_to(path.parents[3])) for block, path in LOCKED_BLOCKS.items()},
        "default_actions": BLOCK_DEFAULT_ACTIONS,
        "authority": authority_label("procedures", detail="blocks.lock inventory"),
    }


@router.get("/capabilities")
def capabilities(principal: Principal = Depends(require_principal)):
    return {
        "ok": True,
        "items": CAPABILITIES,
        "ids": jobs.CAPABILITY_IDS,
        "authority": authority_label("procedures", detail="capability manifest"),
    }


@router.get("/gates")
def gates(principal: Principal = Depends(require_principal)):
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "gates": ["boot", "writer_behaviour", "round_trip", "reuse_accept", "ui_surface"],
        "authority": authority_label("procedures", detail="acceptance gates"),
    }


@router.get("/provenance")
def provenance(principal: Principal = Depends(require_principal)):
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "product": "Harbourline Civil Works",
        "vertical": "product",
        "source_of_record": [
            "document:9624914db39345acbec7ff31dd838d91_harbourline_contract.pdf",
            "document:c5779cac9bcd4e2db8e33a44491360e5_harbourline_boq.xlsx",
        ],
        "precedence": ladder(),
        "authority": authority_label("certified", detail="product provenance"),
    }


@router.post("/work_queue")
def work_queue_enqueue(
    body: Optional[dict] = None,
    principal: Principal = Depends(require_principal),
):
    data = dict(body or {})
    capability_id = str(data.get("capability_id") or "").strip()
    if capability_id not in jobs.CAPABILITY_IDS:
        raise HTTPException(
            status_code=422,
            detail={
                "rejected_field": "capability_id",
                "rejection_reason": "unknown_capability",
                "allowed_values": list(jobs.CAPABILITY_IDS),
            },
        )
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail={"rejected_field": "payload", "rejection_reason": "must_be_an_object"},
        )
    key = data.get("idempotency_key")
    item = work_queue.enqueue(
        capability_id,
        payload,
        idempotency_key=str(key) if key else None,
        tenant_id=principal.tenant_id,
    )
    return {
        "ok": True,
        "item": item,
        "authority": authority_label("block", detail="durable work queue"),
    }


@router.get("/work_queue")
def work_queue_list(
    limit: int = Query(default=100, ge=1, le=1000),
    principal: Principal = Depends(require_principal),
):
    items = work_queue.list_items(principal.tenant_id, limit=limit)
    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "authority": authority_label("source_of_record", detail="caller's queue rows"),
    }


@router.post("/work_queue/{item_id}/process")
async def work_queue_process(
    item_id: int,
    principal: Principal = Depends(require_principal),
):
    claimed = work_queue.claim_pending(item_id, principal.tenant_id)
    if claimed is None:
        existing = work_queue.get(item_id, principal.tenant_id)
        if existing is None:
            raise HTTPException(status_code=404, detail={"error": "queue item not found", "id": item_id})
        raise HTTPException(
            status_code=409,
            detail={"error": "queue item is not pending", "id": item_id, "status": existing.get("status")},
        )
    context = ActionContext(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        organisation_id=principal.tenant_id,
        project_id=principal.tenant_id,
        permissions=["product.process"],
        allowed_domains=["product"],
    )
    result = await execute_action(spec_for(claimed["capability_id"]), context, claimed.get("payload") or {})
    terminal = work_queue.PROCESSED if result.status == ActionStatus.SUCCESS else work_queue.FAILED
    item = work_queue.mark(item_id, terminal, result.to_dict(), from_status=work_queue.PROCESSING)
    return {
        "ok": result.status == ActionStatus.SUCCESS,
        "item": item,
        "result": result.to_dict(),
        "authority": authority_label("block", detail="queued capability execution"),
    }
