"""HTTP surface: one CRUD route set per capability, tenant-scoped.

The route validates only the capability's own declared fields, persists the
accepted request through the tenant store, and never persists a record after
a handler refused. Declared placeholder connectors answer their typed 503
before the handler runs.
"""

from __future__ import annotations

import importlib
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import placeholders, store
from app.models import CAPABILITY_IDS, MODELS, validate_payload
from app.tenancy import Unauthorized, require_principal, reset_current_tenant, set_current_tenant

router = APIRouter()
ROUTE_ENTITIES: Dict[str, str] = {capability_id: capability_id for capability_id in CAPABILITY_IDS}


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})


def _reject(rejection: Dict[str, Any]) -> JSONResponse:
    body = {
        "ok": False,
        "error": rejection.get("reason"),
        "rejected_field": rejection.get("field"),
        "rejection_reason": rejection.get("reason"),
        "allowed_values": rejection.get("allowed_values"),
    }
    headers = {
        "X-Rejected-Field": json.dumps(rejection.get("field")),
        "X-Rejection-Reason": str(rejection.get("reason") or ""),
    }
    if rejection.get("allowed_values"):
        headers["X-Allowed-Values"] = json.dumps(rejection.get("allowed_values"))
    return JSONResponse(status_code=422, content=body, headers=headers)


async def _json_body(request: Request):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _module(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


async def _create(capability_id: str, request: Request) -> JSONResponse:
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()

    missing = placeholders.missing_settings(capability_id)
    if missing:
        return JSONResponse(status_code=503, content=placeholders.refusal(capability_id, missing))

    payload = await _json_body(request)
    if payload is None:
        return _reject({"field": "body", "reason": "not_an_object"})
    normalized, rejection = validate_payload(capability_id, payload)
    if rejection is not None:
        return _reject(rejection)

    token = set_current_tenant(principal.tenant_id)
    try:
        try:
            outcome = _module(capability_id).handle(dict(normalized or {}))
        except Exception as exc:  # noqa: BLE001 -- a handler failure is a typed refusal
            return JSONResponse(
                status_code=200,
                content={"ok": False, "error": f"{type(exc).__name__}: {exc}", "capability_id": capability_id},
            )
    finally:
        reset_current_tenant(token)

    if not isinstance(outcome, dict) or outcome.get("ok") is False:
        failure = outcome if isinstance(outcome, dict) else {"ok": False, "error": "handler returned no result"}
        failure.setdefault("capability_id", capability_id)
        return JSONResponse(status_code=200, content=failure)

    record = dict(normalized or {})
    record.setdefault("status", "open")
    record.setdefault("reference", f"{capability_id}-{uuid.uuid4().hex[:12]}")
    saved = store.save(capability_id, record, tenant_id=principal.tenant_id)
    result = outcome.get("result") or {}
    body = {
        "ok": True,
        "id": saved["id"],
        "record": saved,
        "stored": saved,
        "result": result,
        "capability_id": capability_id,
    }
    if isinstance(result, dict) and result.get("authority"):
        body["authority"] = result["authority"]
    return JSONResponse(status_code=200, content=body)


async def _list(capability_id: str, request: Request) -> JSONResponse:
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    items = store.list_all(capability_id, tenant_id=principal.tenant_id)
    return JSONResponse(status_code=200, content={"ok": True, "items": items, "records": items, "total": len(items)})


async def _read(capability_id: str, record_id: str, request: Request) -> JSONResponse:
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    try:
        identifier = int(record_id)
    except (TypeError, ValueError):
        return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})
    row = store.get(capability_id, identifier, tenant_id=principal.tenant_id)
    if row is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})
    return JSONResponse(status_code=200, content={"ok": True, "record": row, "stored": row, "id": row.get("id")})


async def _delete(capability_id: str, record_id: str, request: Request) -> JSONResponse:
    try:
        principal = require_principal(request)
    except Unauthorized:
        return _unauthorized()
    try:
        identifier = int(record_id)
    except (TypeError, ValueError):
        return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})
    removed = store.delete(capability_id, identifier, tenant_id=principal.tenant_id)
    if not removed:
        return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})
    return JSONResponse(status_code=200, content={"ok": True, "id": identifier, "deleted": True})


def _bind(capability_id: str) -> None:
    async def create(request: Request):
        return await _create(capability_id, request)

    async def list_records(request: Request):
        return await _list(capability_id, request)

    async def read(record_id: str, request: Request):
        return await _read(capability_id, record_id, request)

    async def remove(record_id: str, request: Request):
        return await _delete(capability_id, record_id, request)

    router.add_api_route(f"/v1/{capability_id}", create, methods=["POST"], name=f"create_{capability_id}", operation_id=f"{capability_id}_create")
    router.add_api_route(f"/v1/{capability_id}", list_records, methods=["GET"], name=f"list_{capability_id}", operation_id=f"{capability_id}_list")
    router.add_api_route(f"/v1/{capability_id}/{{record_id}}", read, methods=["GET"], name=f"read_{capability_id}", operation_id=f"{capability_id}_read")
    router.add_api_route(f"/v1/{capability_id}/{{record_id}}", remove, methods=["DELETE"], name=f"delete_{capability_id}", operation_id=f"{capability_id}_delete")


for _capability in CAPABILITY_IDS:
    _bind(_capability)
