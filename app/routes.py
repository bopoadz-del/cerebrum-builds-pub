"""The HTTP surface: one POST/GET pair per capability, tenant-scoped.

Auth first (401), declared connector next (503), then validation (422),
then the handler, then the ROUTE persists the record under the tenant the
principal resolved to. Handlers never save. A handler refusal is HTTP 200
with ok:false; it is never a 500.
"""

from __future__ import annotations

import importlib
import json
from datetime import date
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app import placeholders, store
from app.jobs import CAPABILITIES, KERNEL_JOBS
from app.models import MODELS, STATUS_VALUES
from app.tenancy import Principal, TenantError, resolve_tenant

router = APIRouter()

ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in MODELS.items()}

_MISSING = object()


def principal_of(request: Request) -> Principal:
    try:
        return resolve_tenant(request.headers)
    except TenantError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


AUTH = Depends(principal_of)


def _rejection(field: str, reason: str, allowed=None, message: str = "") -> JSONResponse:
    allowed = list(allowed or [])
    body = {
        "ok": False,
        "rejected_field": field,
        "rejection_reason": reason,
        "allowed_values": allowed,
        "error": message or f"{field}: {reason}",
    }
    headers = {
        "X-Rejected-Field": json.dumps(field),
        "X-Rejection-Reason": reason,
        "X-Allowed-Values": json.dumps(allowed),
    }
    return JSONResponse(status_code=422, content=body, headers=headers)


def _check_type(name: str, value: Any, hint: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if hint is float:
        try:
            float(value)
        except (TypeError, ValueError):
            return "not_a_number"
    elif hint is int:
        try:
            int(value)
        except (TypeError, ValueError):
            return "not_an_integer"
    elif hint is bool:
        if not isinstance(value, bool):
            return "not_a_boolean"
    elif hint is date:
        try:
            date.fromisoformat(str(value)[:10])
        except ValueError:
            return "not_a_date"
    elif hint is str and not isinstance(value, str):
        return "not_a_string"
    return None


def validate(capability_id: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[JSONResponse]]:
    cls = MODELS[capability_id]
    constraints = cls.CONSTRAINTS or {}
    cleaned: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = constraints.get(name) or {}
        value = payload.get(name, _MISSING)
        if value is _MISSING or value in (None, ""):
            if rules.get("required"):
                return None, _rejection(name, "missing_required",
                                        message=f"{name} is required")
            cleaned[name] = None
            continue
        allowed = rules.get("allowed_values")
        if allowed and str(value) not in [str(item) for item in allowed]:
            return None, _rejection(name, "not_allowed", allowed,
                                    f"{name} must be one of: " + ", ".join(str(a) for a in allowed))
        hint = type(getattr(cls, name, ""))
        problem = _check_type(name, value, hint)
        if problem:
            return None, _rejection(name, problem, message=f"{name}: {problem}")
        cleaned[name] = value
    return cleaned, None


def _handler(capability_id: str):
    module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))
    return module


@router.get("/v1/capabilities")
async def capabilities(principal: Principal = AUTH) -> Any:
    items = [
        {
            "id": cap["id"],
            "entity": cap["entity"],
            "title": cap["title"],
            "summary": cap["summary"],
            "blocks": cap["blocks"],
            "placeholder": cap["placeholder"] or None,
            "persists": not bool(cap["placeholder"]),
            "status_values": STATUS_VALUES,
            "fields": list(MODELS[cap["id"]].FIELDS),
        }
        for cap in CAPABILITIES
    ]
    return {"ok": True, "items": items, "total": len(items), "authority": "2:documents"}


@router.get("/v1/jobs")
async def jobs(principal: Principal = AUTH) -> Any:
    return {"ok": True, "jobs": KERNEL_JOBS, "authority": "1:certified"}


@router.get("/v1/catalog")
async def catalog(principal: Principal = AUTH) -> Any:
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "items": [{"block": block, "capability": cap["id"]}
                  for cap in CAPABILITIES for block in cap["blocks"]],
        "authority": "1:certified",
    }


@router.get("/v1/inventory")
async def inventory(principal: Principal = AUTH) -> Any:
    from app.dispatch import LOCKED_BLOCKS

    return {
        "ok": True,
        "kernel": "CLONER",
        "lock": {"blocks": LOCKED_BLOCKS},
        "items": sorted({block for cap in CAPABILITIES for block in cap["blocks"]}),
        "authority": "1:certified",
    }


@router.get("/v1/gates")
async def gates(principal: Principal = AUTH) -> Any:
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "gates": [
            {"name": "writer_behaviour", "status": "pending"},
            {"name": "product_gate", "status": "pending"},
            {"name": "store_gate", "status": "pending"},
        ],
        "authority": "1:certified",
    }


@router.get("/v1/provenance")
async def provenance(principal: Principal = AUTH) -> Any:
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "product_id": "product",
        "product_name": "Harbourline Civil Works contracts administration",
        "sources": [
            "document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf",
            "document:a903d4ccba764b6f84b39e65b8b6add3_harbourline_boq.xlsx",
        ],
        "authority": "1:certified",
    }


@router.post("/v1/{capability_id}")
async def create_record(capability_id: str, request: Request,
                        principal: Principal = AUTH) -> Any:
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail="unknown capability")
    try:
        payload = await request.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return _rejection("payload", "not_an_object", message="a JSON object is required")

    declared = placeholders.PLACEHOLDER_CONNECTORS.get(capability_id)
    if declared:
        return JSONResponse(status_code=503, content=placeholders.refusal_body(capability_id))

    cleaned, failure = validate(capability_id, payload)
    if failure is not None:
        return failure

    module = _handler(capability_id)
    result = module.handle(cleaned, tenant_id=principal.tenant_id,
                           principal_id=principal.principal_id)
    if not isinstance(result, dict) or result.get("ok") is not True:
        body = dict(result or {})
        body.setdefault("ok", False)
        body.setdefault("capability_id", capability_id)
        body.setdefault("error", "handler refused the request")
        return JSONResponse(status_code=200, content=body)

    entity = ROUTE_ENTITIES[capability_id]
    record = {name: cleaned.get(name) for name in store.COLUMNS[entity]}
    computed = result.get("result") if isinstance(result.get("result"), dict) else {}
    for key, value in computed.items():
        if key in record and record[key] in (None, "") and isinstance(value, (str, int, float, bool)):
            record[key] = value
    stored = store.save(entity, record, tenant_id=principal.tenant_id)
    return {
        "ok": True,
        "capability_id": capability_id,
        "entity": entity,
        "tenant_id": principal.tenant_id,
        "record": stored,
        "stored": stored,
        "id": stored.get("id"),
        "result": computed,
        "authority": result.get("authority"),
        "source": result.get("source"),
    }


@router.get("/v1/{capability_id}")
async def list_records(capability_id: str, principal: Principal = AUTH) -> Any:
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail="unknown capability")
    entity = ROUTE_ENTITIES[capability_id]
    rows = store.list_all(entity, tenant_id=principal.tenant_id)
    return {"ok": True, "capability_id": capability_id, "entity": entity,
            "items": rows, "total": len(rows), "authority": "2:documents"}


@router.get("/v1/{capability_id}/{record_id}")
async def get_record(capability_id: str, record_id: int,
                     principal: Principal = AUTH) -> Any:
    if capability_id not in MODELS:
        raise HTTPException(status_code=404, detail="unknown capability")
    entity = ROUTE_ENTITIES[capability_id]
    row = store.get(entity, int(record_id), tenant_id=principal.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True, "capability_id": capability_id, "entity": entity,
            "record": row, "authority": "2:documents"}
