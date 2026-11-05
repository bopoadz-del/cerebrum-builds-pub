"""HTTP routes over the capability handlers.

One route table, one tenant per request. A record is saved by the route from
the authenticated principal's tenant -- handlers never write to the store
themselves, so a handler cannot forget the tenant.
"""

from __future__ import annotations

import importlib
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import store
from app.authority import authority_label
from app.models import MODELS
from app.placeholders import PLACEHOLDERS, refusal_body, settings_for
from app.security import authenticate, require_capability_write, validate_payload

router = APIRouter(prefix="/v1", tags=["capabilities"])

ROUTE_ENTITIES: Dict[str, str] = {cap: getattr(cls, "ENTITY", cap) for cap, cls in MODELS.items()}


def _handler(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


def _rejection(exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    body = {
        "ok": False,
        "error": "validation_error",
        **detail,
    }
    headers = {
        "X-Rejected-Field": str(detail.get("rejected_field", "")),
        "X-Rejection-Reason": str(detail.get("rejection_reason", "")),
    }
    if detail.get("allowed_values"):
        headers["X-Allowed-Values"] = json.dumps(detail["allowed_values"])
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@router.post("/{capability_id}")
async def create_record(capability_id: str, request: Request) -> Any:
    principal = authenticate(request.headers)
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail={"error": "unknown capability"})
    require_capability_write(principal, capability_id)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail={"error": "payload must be an object"})
    # A declared placeholder refuses before the handler runs and stores
    # nothing; the rest of its surface still answers. The refusal is the
    # authoritative answer for this capability in this build, so it is not
    # pre-empted by field validation of a connector-shaped sample.
    if capability_id in PLACEHOLDERS:
        return JSONResponse(
            status_code=503,
            content=refusal_body(capability_id),
            headers={"X-Placeholder-Settings": ",".join(settings_for(capability_id))},
        )
    try:
        validate_payload(MODELS[capability_id], payload)
    except HTTPException as exc:
        return _rejection(exc)

    module = _handler(capability_id)
    result = module.handle(
        {
            **payload,
            "_tenant_id": principal.tenant_id,
            "_principal_id": principal.user_id,
            "_roles": list(principal.roles),
        }
    )
    if not isinstance(result, dict):
        result = {"ok": False, "error": "handler returned no result"}
    if result.get("ok") is False:
        body = dict(result)
        body.setdefault("authority", authority_label(1))
        return JSONResponse(status_code=200, content=body)

    entity = ROUTE_ENTITIES[capability_id]
    record = dict(payload)
    record.update(result.get("record") or {})
    record.pop("_tenant_id", None)
    record.pop("_principal_id", None)
    record.pop("_roles", None)
    stored = await run_in_threadpool(store.save, entity, record, principal.tenant_id)
    body = dict(result)
    body["id"] = stored["id"]
    body["record"] = stored
    body["stored"] = stored
    return JSONResponse(status_code=200, content=body)


@router.get("/{capability_id}")
def list_records(capability_id: str, request: Request) -> Any:
    principal = authenticate(request.headers)
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail={"error": "unknown capability"})
    entity = ROUTE_ENTITIES[capability_id]
    rows = store.list_all(entity, principal.tenant_id)
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "capability_id": capability_id,
            "entity": entity,
            "items": rows,
            "total": len(rows),
            "authority": authority_label(1),
        },
    )


@router.get("/{capability_id}/{record_id}")
def get_record(capability_id: str, record_id: int, request: Request) -> Any:
    principal = authenticate(request.headers)
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail={"error": "unknown capability"})
    entity = ROUTE_ENTITIES[capability_id]
    row = store.get(entity, record_id, principal.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "record not found"})
    return JSONResponse(
        status_code=200,
        content={"ok": True, "capability_id": capability_id, "record": row, "authority": authority_label(1)},
    )


@router.patch("/{capability_id}/{record_id}")
async def update_record(capability_id: str, record_id: int, request: Request) -> Any:
    principal = authenticate(request.headers)
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail={"error": "unknown capability"})
    require_capability_write(principal, capability_id)
    try:
        changes = await request.json()
    except Exception:
        changes = {}
    if not isinstance(changes, dict):
        raise HTTPException(status_code=422, detail={"error": "payload must be an object"})
    entity = ROUTE_ENTITIES[capability_id]
    updated = store.update(entity, record_id, changes, principal.tenant_id)
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "record not found"})
    return JSONResponse(status_code=200, content={"ok": True, "record": updated})


@router.delete("/{capability_id}/{record_id}")
async def delete_record(capability_id: str, record_id: int, request: Request) -> Any:
    principal = authenticate(request.headers)
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail={"error": "unknown capability"})
    require_capability_write(principal, capability_id)
    entity = ROUTE_ENTITIES[capability_id]
    deleted = store.delete(entity, record_id, principal.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "record not found"})
    return JSONResponse(status_code=200, content={"ok": True, "deleted": record_id})
