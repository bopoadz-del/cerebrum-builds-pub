"""Platform registers: the roster, the lock, the ladder and the summary."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app import contract_terms, formulas, jobs, store
from app.authority import label, ladder
from app.models import MODELS
from app.security import require_principal
from app.tenancy import Principal, tenant_of

router = APIRouter()


@router.get("/v1/jobs")
def job_roster(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return {"ok": True, "jobs": jobs.JOBS}


@router.get("/v1/catalog")
def catalog(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(jobs.CATALOG, ok=True)


@router.get("/v1/inventory")
def inventory(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(jobs.INVENTORY, ok=True)


@router.get("/v1/capabilities")
def capabilities(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return {"ok": True, "items": jobs.CAPABILITIES}


@router.get("/v1/gates")
def gates(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(jobs.GATES, ok=True)


@router.get("/v1/provenance")
def provenance(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(jobs.PROVENANCE, ok=True)


@router.get("/v1/terms")
def terms(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(contract_terms.cited_terms(), ok=True, authority=label("documents"))


@router.get("/v1/formulas")
def formula_catalogue(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    return dict(formulas.catalogue(), ok=True, authority=label("formulas"), ladder=ladder())


@router.get("/v1/summary")
def summary(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    tenant_id = tenant_of(principal)
    counts: Dict[str, int] = {}
    latest: Dict[str, Any] = {}
    for capability_id in MODELS:
        rows = store.list_all(capability_id, tenant_id)
        counts[capability_id] = len(rows)
        latest[capability_id] = rows[-1] if rows else None
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "counts": counts,
        "latest": latest,
        "authority": label("formulas"),
    }
