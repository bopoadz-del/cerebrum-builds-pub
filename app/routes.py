"""Kernel roster and product metadata endpoints (all authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import jobs
from app.authority import authority_label, ladder
from app.jobs import CAPABILITIES
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
