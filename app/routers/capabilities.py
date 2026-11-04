"""HTTP routes over the capability handlers."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app import store
from app.models import MODELS
from app.security import rejection_body, rejection_headers, require_principal
from app.tenancy import Principal, tenant_of

router = APIRouter()

ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in MODELS.items()}

_log = logging.getLogger("platform.capability")


def _refuse_validation(field: str, reason: str, detail: str, allowed: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=rejection_body(field, reason, detail, allowed),
        headers=rejection_headers(field, reason, allowed),
    )


def _module(capability_id: str):
    name = "app.actions." + str(capability_id)
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise HTTPException(status_code=404, detail="unknown capability: %s" % capability_id) from exc


def _capability(capability_id: str):
    cls = MODELS.get(str(capability_id))
    if cls is None:
        raise HTTPException(status_code=404, detail="unknown capability: %s" % capability_id)
    return cls


@router.get("/v1/capabilities.json")
def capability_contracts(principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    """The declared contract of every capability, for the console."""
    return {
        "ok": True,
        "items": [
            {
                "id": capability_id,
                "entity": cls.ENTITY,
                "fields": [
                    {
                        "name": name,
                        "type": cls.TYPES.get(name, "str"),
                        **(cls.CONSTRAINTS.get(name) or {}),
                    }
                    for name in cls.FIELDS
                ],
            }
            for capability_id, cls in MODELS.items()
        ],
    }


@router.get("/v1/{capability_id}")
def list_records(capability_id: str, principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    _capability(capability_id)
    rows = store.list_all(str(capability_id), tenant_of(principal))
    return {"ok": True, "items": rows, "records": rows, "total": len(rows)}


@router.get("/v1/{capability_id}/{record_id}")
def get_record(capability_id: str, record_id: str,
               principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    _capability(capability_id)
    row = store.get(str(capability_id), record_id, tenant_of(principal))
    if row is None:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True, "record": row, "stored": row, "id": row.get("id")}


@router.post("/v1/{capability_id}")
def create_record(
    capability_id: str,
    request: Request,
    body: Dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    cls = _capability(capability_id)
    payload = dict(body or {})
    clean, rejection = cls.validate(payload)
    if rejection is not None:
        return _refuse_validation(
            rejection.get("rejected_field") or "payload",
            rejection.get("rejection_reason") or "invalid",
            rejection.get("detail") or "invalid payload",
            rejection.get("allowed_values"),
        )
    module = _module(capability_id)
    tenant_id = tenant_of(principal)
    try:
        outcome = module.handle(dict(clean), tenant_id=tenant_id)
    except Exception as exc:  # noqa: BLE001 - a handler failure is a refusal, not a 500
        _log.exception("capability %s failed", capability_id)
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "capability_id": capability_id,
                "error": "handler refused: %s" % type(exc).__name__,
            },
        )
    if not isinstance(outcome, dict) or outcome.get("ok") is False:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "capability_id": capability_id,
                "error": str((outcome or {}).get("error") if isinstance(outcome, dict) else "handler refused")[:300],
            },
        )
    stored = store.save(str(capability_id), clean, tenant_id)
    return {
        "ok": True,
        "capability_id": capability_id,
        "tenant_id": tenant_id,
        "record": stored,
        "stored": stored,
        "id": stored.get("id"),
        "computed": outcome.get("computed") or {},
        "blocks": outcome.get("blocks") or {},
        "authority": outcome.get("authority") or {},
    }


@router.delete("/v1/{capability_id}/{record_id}")
def delete_record(capability_id: str, record_id: str,
                  principal: Principal = Depends(require_principal)) -> Dict[str, Any]:
    _capability(capability_id)
    removed = store.delete(str(capability_id), record_id, tenant_of(principal))
    if not removed:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True, "deleted": True, "id": record_id}
