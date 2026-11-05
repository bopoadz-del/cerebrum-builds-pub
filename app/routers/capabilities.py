"""Capability HTTP surface: authenticated, tenant-scoped, schema-validated."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app import jobs, store
from app.actions import (
    delay_damages_tracking,
    document_register,
    progress_claim_administration,
    qa_itp_records,
)
from app.authority import authority_label
from app.models import MODELS, coerce_value
from app.security import require_principal
from app.tenancy import Principal

router = APIRouter(prefix="/v1", tags=["capabilities"])

HANDLERS = {
    "progress_claim_administration": progress_claim_administration,
    "delay_damages_tracking": delay_damages_tracking,
    "qa_itp_records": qa_itp_records,
    "document_register": document_register,
}

ROUTE_ENTITIES = {item["id"]: item["entity"] for item in jobs.CAPABILITIES}


def _reject(field: str, reason: str, allowed=None):
    detail = {
        "rejected_field": field,
        "rejection_reason": reason,
        "allowed_values": list(allowed) if allowed else None,
    }
    headers = {
        "X-Rejected-Field": json.dumps(field),
        "X-Rejection-Reason": reason,
    }
    if allowed:
        headers["X-Allowed-Values"] = json.dumps(list(allowed))
    raise HTTPException(status_code=422, detail=detail, headers=headers)


def validate_payload(capability_id: str, payload: Any) -> dict:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        _reject("body", "must_be_an_object")
    model = MODELS[capability_id]
    clean = {}
    for field in model.FIELDS:
        rules = model.CONSTRAINTS.get(field) or {}
        value = payload.get(field)
        if value in (None, "") and rules.get("required"):
            _reject(field, "missing_required", rules.get("allowed_values"))
        try:
            clean[field] = coerce_value(capability_id, field, value)
        except ValueError as exc:
            _reject(field, "not_allowed" if rules.get("allowed_values") else "invalid_value", rules.get("allowed_values"))
            raise exc
    return clean


def _handler(capability_id: str):
    module = HANDLERS.get(capability_id)
    if module is None:
        raise HTTPException(status_code=404, detail={"error": "unknown capability", "capability_id": capability_id})
    return module


@router.post("/{capability_id}")
def create_capability_record(
    capability_id: str,
    body: Optional[dict] = None,
    principal: Principal = Depends(require_principal),
):
    module = _handler(capability_id)
    clean = validate_payload(capability_id, body)
    try:
        result = module.handle(clean)
    except Exception as exc:  # noqa: BLE001 -- a failed capability is a refusal
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "capability_id": capability_id,
                "authority": authority_label("block", detail="capability handler"),
            },
        )
    if not isinstance(result, dict) or result.get("ok") is False:
        body_out = dict(result or {})
        body_out.setdefault("capability_id", capability_id)
        body_out["ok"] = False
        body_out.setdefault("authority", authority_label("block", detail="capability refusal"))
        return JSONResponse(status_code=200, content=body_out)

    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    write_record = dict(clean)
    for key, value in record.items():
        if key not in ("id", "tenant_id") and value is not None and write_record.get(key) is None:
            write_record[key] = value
    saved = store.save(ROUTE_ENTITIES[capability_id], write_record, principal.tenant_id)
    response = {
        "ok": True,
        "record": saved,
        "stored": saved,
        "id": saved.get("id"),
        "capability_id": capability_id,
        "authority": result.get("authority") or authority_label("source_of_record", detail=capability_id),
        "tenant": principal.tenant_id,
    }
    for key, value in result.items():
        if key not in ("ok", "record", "id", "stored"):
            response.setdefault(key, value)
    return response


@router.get("/{capability_id}")
def list_capability_records(
    capability_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    q: Optional[str] = None,
    principal: Principal = Depends(require_principal),
):
    _handler(capability_id)
    rows = store.query(ROUTE_ENTITIES[capability_id], principal.tenant_id, q=q, limit=limit)
    return {
        "ok": True,
        "items": rows,
        "records": rows,
        "count": len(rows),
        "capability_id": capability_id,
        "authority": authority_label("source_of_record", detail="persisted register rows"),
    }


@router.get("/{capability_id}/{record_id}")
def get_capability_record(
    capability_id: str,
    record_id: int,
    principal: Principal = Depends(require_principal),
):
    _handler(capability_id)
    row = store.get(ROUTE_ENTITIES[capability_id], record_id, principal.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "record not found", "id": record_id})
    return {
        "ok": True,
        "record": row,
        "stored": row,
        "id": row.get("id"),
        "capability_id": capability_id,
        "authority": authority_label("source_of_record", detail="persisted register row"),
    }


@router.put("/{capability_id}/{record_id}")
def update_capability_record(
    capability_id: str,
    record_id: int,
    body: Optional[dict] = None,
    principal: Principal = Depends(require_principal),
):
    _handler(capability_id)
    current = store.get(ROUTE_ENTITIES[capability_id], record_id, principal.tenant_id)
    if current is None:
        raise HTTPException(status_code=404, detail={"error": "record not found", "id": record_id})
    merged = dict(current)
    merged.update(body or {})
    clean = validate_payload(capability_id, merged)
    saved = store.update(ROUTE_ENTITIES[capability_id], record_id, clean, principal.tenant_id)
    if saved is None:
        raise HTTPException(status_code=404, detail={"error": "record not found", "id": record_id})
    return {"ok": True, "record": saved, "stored": saved, "id": record_id, "authority": authority_label("source_of_record")}


@router.delete("/{capability_id}/{record_id}")
def delete_capability_record(
    capability_id: str,
    record_id: int,
    principal: Principal = Depends(require_principal),
):
    _handler(capability_id)
    if not store.delete(ROUTE_ENTITIES[capability_id], record_id, principal.tenant_id):
        raise HTTPException(status_code=404, detail={"error": "record not found", "id": record_id})
    return {"ok": True, "id": record_id, "deleted": True, "authority": authority_label("source_of_record")}
