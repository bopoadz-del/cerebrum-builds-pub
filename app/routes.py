"""The platform's HTTP surface: one tenant-scoped route family per capability.

Shape of a capability route, and the reason for each part:
  * authenticate at the edge (401 without a token);
  * answer the DECLARED placeholder refusal (503, typed) before validation;
  * validate the payload against the capability's own model -- a missing
    required field or an out-of-vocabulary value is 422 with the field named;
  * run the handler, and refuse with its answer when it fails closed;
  * persist the REQUEST through the tenant-scoped store (never the handler,
    which has no tenant), then answer {ok, id, record, result, authority}.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app import (
    authority,
    config,
    dispatch,
    domain_ops,
    jobs,
    placeholders,
    retrieval,
    security,
    store,
    work_queue,
)
from app.models import MODELS
from app.validation import validate_payload

#: Static kernel surfaces. Registered BEFORE the capability family, so
#: /v1/jobs is never read as a capability id.
KERNEL = APIRouter(prefix="/v1", tags=["kernel"])
#: The capability family: /v1/{capability_id} and its record routes.
ROUTER = APIRouter(prefix="/v1", tags=["capabilities"])

#: capability -> the entity its route saves to. The entity IS the capability id
#: (the stem of its handler module), declared here so a reader never guesses.
ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in MODELS.items()}


def _field_specs(capability_id: str) -> List[Dict[str, Any]]:
    """The fields this capability declares -- what the console builds its form from."""
    model = MODELS.get(capability_id)
    if model is None:
        return []
    constraints = getattr(model, "CONSTRAINTS", {}) or {}
    rows: List[Dict[str, Any]] = []
    for name in model.FIELDS:
        spec = dict(constraints.get(name) or {})
        row: Dict[str, Any] = {
            "name": name,
            "type": spec.get("type", "str"),
            "required": bool(spec.get("required")),
        }
        for key in ("allowed_values", "min", "max", "format", "max_length"):
            if key in spec:
                row[key] = spec[key]
        rows.append(row)
    return rows


def _module(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


def _rejection(violation: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=security.rejected(violation),
        headers=security.rejection_headers(violation),
    )


def _refusal(result: Dict[str, Any]) -> JSONResponse:
    kind = str(result.get("error_kind") or "refused")
    body = {
        "ok": False,
        "error": str(result.get("error") or "the capability refused"),
        "error_kind": kind,
    }
    if result.get("blocks"):
        body["blocks"] = result["blocks"]
    if kind == "invalid_track":
        field = str(result.get("field_path") or "yaml_text")
        body["rejected_field"] = field
        body["rejection_reason"] = "invalid_document"
        if result.get("schema_errors"):
            body["schema_errors"] = result["schema_errors"]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body,
            headers={
                "X-Rejected-Field": __import__("json").dumps(field),
                "X-Rejection-Reason": "invalid_document",
            },
        )
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=body)


def _create(capability_id: str, payload: Dict[str, Any], principal) -> JSONResponse:
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    placeholder = placeholders.refusal(capability_id)
    if placeholder is not None:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=placeholder)

    values, violations = validate_payload(model, payload)
    if violations:
        return _rejection(violations[0])

    module = _module(capability_id)
    if not hasattr(module, "handle"):
        raise HTTPException(status_code=501, detail="capability has no handler")

    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if idempotency_key:
        hit = work_queue.recall(idempotency_key, principal.tenant_id)
        if hit is not None:
            existing = store.get(str(hit.get("entity")), hit.get("record_id"), tenant_id=principal.tenant_id)
            if existing is not None:
                return JSONResponse(
                    status_code=200,
                    content={
                        "ok": True,
                        "capability_id": capability_id,
                        "id": existing.get("id"),
                        "stored": existing,
                        "record": existing,
                        "replayed": True,
                        "authority": authority.label(3),
                    },
                )

    handler_payload = dict(values)
    handler_payload["reference"] = values.get("reference") or ""
    handler_payload["_tenant_id"] = principal.tenant_id
    result = module.handle(handler_payload)
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="capability returned an invalid answer")
    if result.get("ok") is not True:
        return _refusal(result)

    stored = store.save(model.ENTITY, values, tenant_id=principal.tenant_id)
    if idempotency_key:
        work_queue.remember(idempotency_key, model.ENTITY, stored["id"], principal.tenant_id)
    body = {
        "ok": True,
        "capability_id": capability_id,
        "id": stored.get("id"),
        "stored": stored,
        "record": stored,
        "result": result.get("result"),
        "authority": result.get("authority") or authority.label(3),
        "tenant_id": principal.tenant_id,
    }
    return JSONResponse(status_code=200, content=body)


@ROUTER.post("/{capability_id}")
def create_capability_record(capability_id: str, request: Request, payload: Optional[Dict[str, Any]] = None):
    principal = security.principal_from_request(request)
    return _create(capability_id, dict(payload or {}), principal)


@ROUTER.get("/{capability_id}")
def list_capability_records(capability_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    items = store.list_all(model.ENTITY, tenant_id=principal.tenant_id)
    return {
        "ok": True,
        "capability_id": capability_id,
        "entity": model.ENTITY,
        "items": items,
        "total": len(items),
    }


@ROUTER.get("/{capability_id}/{item_id}")
def read_capability_record(capability_id: str, item_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    record = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if record is None:
        raise security.not_found("record")
    return {"ok": True, "capability_id": capability_id, "record": record}


@ROUTER.put("/{capability_id}/{item_id}")
def update_capability_record(capability_id: str, item_id: str, payload: Dict[str, Any], request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    existing = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if existing is None:
        raise security.not_found("record")
    merged = {key: existing.get(key) for key in model.FIELDS if existing.get(key) is not None}
    merged.update({key: value for key, value in (payload or {}).items() if key in model.FIELDS})
    values, violations = validate_payload(model, merged)
    if violations:
        return _rejection(violations[0])
    updated = store.update(model.ENTITY, item_id, values, tenant_id=principal.tenant_id)
    if updated is None:
        raise security.not_found("record")
    return {"ok": True, "capability_id": capability_id, "id": updated.get("id"), "record": updated}


@ROUTER.delete("/{capability_id}/{item_id}")
def delete_capability_record(capability_id: str, item_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    record = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if record is None:
        raise security.not_found("record")
    if not store.delete(model.ENTITY, item_id, tenant_id=principal.tenant_id):
        raise security.not_found("record")
    return {"ok": True, "capability_id": capability_id, "deleted": True, "id": record.get("id")}


# --- kernel surfaces -------------------------------------------------------


@KERNEL.get("/jobs")
def kernel_jobs(request: Request):
    security.principal_from_request(request)
    return {"ok": True, "jobs": jobs.KERNEL_JOBS}


@KERNEL.get("/catalog")
def kernel_catalog(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "blocks": list(dispatch.BLOCK_IDS),
        "contracts": [
            {
                "block": block_id,
                "path": str(dispatch.block_path(block_id)),
                "default_action": dispatch.BLOCK_DEFAULT_ACTIONS.get(block_id),
            }
            for block_id in dispatch.BLOCK_IDS
        ],
    }


@KERNEL.get("/inventory")
def kernel_inventory(request: Request):
    security.principal_from_request(request)
    absent = dispatch.missing_blocks()
    return {
        "ok": True,
        "kernel": "CLONER",
        "lock": {
            "file": str(dispatch.LOCK_FILE),
            "vendored_root": str(dispatch.VENDOR_ROOT),
            "present_in_checkout": dispatch.vendor_tree_present(),
            "missing": absent,
        },
        "blocks": [
            {"block": block_id, "path": str(dispatch.block_path(block_id)), "present": block_id not in absent}
            for block_id in dispatch.BLOCK_IDS
        ],
    }


@KERNEL.get("/capabilities")
def capability_roster(request: Request):
    security.principal_from_request(request)
    items = []
    for item in jobs.CAPABILITIES:
        entry = dict(item)
        entry["placeholder_connectors"] = placeholders.connectors_for(item["id"])
        entry["servable"] = not bool(placeholders.missing_connectors(item["id"]))
        entry["fields"] = _field_specs(item["id"])
        entry["stages"] = [order["stage"] for order in jobs.ORDERS if order["capability"] == item["id"]]
        items.append(entry)
    return {"ok": True, "items": items, "total": len(items)}


@KERNEL.get("/gates")
def kernel_gates(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "gates": [
            {"id": "code", "runs": "pytest -m 'not pilot'"},
            {"id": "product", "runs": "pytest -m pilot against the booted product"},
            {"id": "store", "runs": "scripts/acceptance.py inside the built image"},
        ],
    }


@KERNEL.get("/provenance")
def kernel_provenance(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "product": config.ROOT.name,
        "blocks": [{"block": block_id, "path": str(dispatch.block_path(block_id))} for block_id in dispatch.BLOCK_IDS],
        "entities": ROUTE_ENTITIES,
        "placeholders": placeholders.PLACEHOLDER_CONNECTORS,
    }


@KERNEL.get("/authority")
def authority_ladder(request: Request):
    security.principal_from_request(request)
    ladder = authority.ladder()
    return {
        "ok": True,
        "ladder": {str(layer): rank for layer, rank in sorted(ladder.items())},
        "labels": {str(layer): authority.layer_label(layer) for layer in ladder},
        "rule": "layer 1 certified > 2 documents > 3 formulas > 4 procedures",
    }


@KERNEL.get("/formulas")
def formula_catalog(request: Request):
    security.principal_from_request(request)
    from app import formulas

    return {
        "ok": True,
        "definitions": [
            {"id": key, "label": row["label"], "expression": row["expression"], "source": row["source"]}
            for key, row in formulas.WRITER_DEFINITIONS.items()
        ],
    }


@KERNEL.get("/queue")
def queue_items(request: Request):
    principal = security.principal_from_request(request)
    items = work_queue.list_items(tenant_id=principal.tenant_id)
    return {"ok": True, "items": items, "total": len(items)}


@KERNEL.post("/queue")
def queue_enqueue(payload: Dict[str, Any], request: Request):
    principal = security.principal_from_request(request)
    capability_id = str((payload or {}).get("capability_id") or "")
    if capability_id not in MODELS:
        raise security.not_found("capability")
    item = work_queue.enqueue(
        capability_id,
        dict((payload or {}).get("payload") or {}),
        idempotency_key=(payload or {}).get("idempotency_key"),
        tenant_id=principal.tenant_id,
    )
    return {"ok": True, "item": item}


@KERNEL.post("/queue/{item_id}/process")
def queue_process(item_id: str, request: Request):
    principal = security.principal_from_request(request)
    outcome = domain_ops.perform("process", "", {"id": item_id}, context=domain_ops.authorized_context())
    if outcome.get("status") != "success":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"ok": False, "error": outcome.get("error_message") or "queue item not processable", "outcome": outcome},
        )
    return {"ok": True, "outcome": outcome}


@KERNEL.get("/library/search")
def library_search(request: Request, q: str = "", limit: int = 5):
    principal = security.principal_from_request(request)
    return retrieval.answer(q, principal.tenant_id, limit=max(1, min(20, int(limit))))
