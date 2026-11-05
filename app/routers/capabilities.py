"""Capability HTTP surface: one create, list, read and delete per capability.

Authentication precedes validation, the tenant comes from the principal, and
a refusal is answered as data -- never a 500 and never a record the caller's
tenant cannot see.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app import jobs, security, store, tenancy

router = APIRouter(tags=["capabilities"])


def current_tenant(request: Request) -> tenancy.Tenant:
    try:
        return tenancy.resolve_tenant(request.headers)
    except tenancy.Unauthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _handler(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


def _rejection(exc: security.Refusal) -> JSONResponse:
    allowed = None
    body = security.error_body(exc.message, field=exc.field, allowed=allowed)
    headers = security.rejection_headers(exc.field or "", "missing_required" if "required" in exc.message else "invalid", allowed)
    return JSONResponse(status_code=exc.status, content=body, headers=headers)


def _known(capability_id: str) -> str:
    entity = jobs.ROUTE_ENTITIES.get(capability_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"unknown capability: {capability_id}")
    return entity


@router.post("/v1/{capability_id}")
async def create_record(
    capability_id: str,
    request: Request,
    payload: Dict[str, Any] = Body(default_factory=dict),
    tenant: tenancy.Tenant = Depends(current_tenant),
) -> Any:
    entity = _known(capability_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")
    try:
        cleaned = security.validate_payload(capability_id, payload)
    except security.Refusal as exc:
        return _rejection(exc)

    try:
        module = _handler(capability_id)
        outcome = module.handle(cleaned, tenant_id=tenant.tenant_id)
    except security.Refusal as exc:
        return _rejection(exc)
    except Exception as exc:  # noqa: BLE001 - a handler must not 500 the edge
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "rejected_field": None,
            },
        )

    if not isinstance(outcome, dict) or outcome.get("ok") is False:
        body = dict(outcome or {})
        body.setdefault("ok", False)
        body.setdefault("error", "refused")
        return JSONResponse(status_code=200, content=body)

    record = outcome.get("record") or cleaned
    stored = store.save(entity, {**cleaned, **record}, tenant_id=tenant.tenant_id)
    return {
        "ok": True,
        "entity": entity,
        "id": stored["id"],
        "record": stored,
        "stored": stored,
        "result": outcome.get("result"),
    }


@router.get("/v1/{capability_id}")
async def list_records(
    capability_id: str,
    tenant: tenancy.Tenant = Depends(current_tenant),
) -> Dict[str, Any]:
    entity = _known(capability_id)
    items = store.list_all(entity, tenant_id=tenant.tenant_id)
    return {"ok": True, "entity": entity, "items": items, "total": len(items)}


@router.get("/v1/{capability_id}/{record_id}")
async def read_record(
    capability_id: str,
    record_id: int,
    tenant: tenancy.Tenant = Depends(current_tenant),
) -> Dict[str, Any]:
    entity = _known(capability_id)
    if not store.valid_id(record_id):
        raise HTTPException(status_code=404, detail="record not found")
    row = store.get(entity, record_id, tenant_id=tenant.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True, "entity": entity, "record": row, "id": row.get("id")}


@router.delete("/v1/{capability_id}/{record_id}")
async def delete_record(
    capability_id: str,
    record_id: int,
    tenant: tenancy.Tenant = Depends(current_tenant),
) -> Dict[str, Any]:
    entity = _known(capability_id)
    if not store.valid_id(record_id):
        raise HTTPException(status_code=404, detail="record not found")
    removed = store.delete(entity, record_id, tenant_id=tenant.tenant_id)
    if not removed:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True, "entity": entity, "deleted": record_id}
