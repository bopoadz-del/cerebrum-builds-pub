"""HTTP surface for the the project platform.

Every /v1 route is authenticated (401 with no token); validation failures are
422 naming the field; only a declared vocabulary is accepted. The ROUTE owns
the tenant-scoped save -- a handler never persists. A read that finds another
tenant's record answers 404: existence is not leaked.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app import jobs, store
from app.auth import (
    reject_invalid_payload,
    reject_reserved_payload_keys,
    reject_unknown_approver,
    require_platform_token,
    require_read_token,
)
from app.models import MODELS
from app.tenancy import bind_tenant, release_tenant

router = APIRouter()

CAPABILITY_IDS = sorted(MODELS)
ENTITY_OF = {cap: getattr(cls, "ENTITY", cap) for cap, cls in sorted(MODELS.items())}
ROUTE_ENTITIES = dict(ENTITY_OF)

READ_AUTHORITY: Dict[str, Dict[str, Any]] = {
    cap: {"layer": 1 if cap == "contract_source_of_record" else 2,
          "name": "documents",
          "source": "app/actions/%s.py" % cap}
    for cap in CAPABILITY_IDS
}
READ_AUTHORITY["contract_compliance_gate"] = {
    "layer": 1, "name": "certified", "source": "app/actions/contract_compliance_gate.py"
}

LIST_CONTROLS = ("limit", "offset", "sort", "order")


def _require_identity(request: Request) -> None:
    require_platform_token(request)


def _run(cap_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    module = importlib.import_module("app.actions." + cap_id)
    return module.handle(payload)


def _labelled(capability_id: str, body: Any) -> Any:
    if not isinstance(body, dict):
        return body
    out = dict(body)
    label = READ_AUTHORITY.get(str(capability_id))
    if label is not None and "authority" not in out:
        out["authority"] = dict(label)
    return out


def _error(cap_id: str, exc: Exception) -> Dict[str, Any]:
    """A stable refusal; diagnostics stay in the server log."""
    import logging

    logging.getLogger("platform.error").exception(
        "capability %s raised %s", cap_id, type(exc).__name__
    )
    return {
        "ok": False,
        "capability": cap_id,
        "error_kind": "internal_error",
        "error": "the platform could not complete this request (%s)" % cap_id,
    }


@router.get("/jobs")
def list_jobs(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return {"jobs": jobs.JOBS}


@router.get("/catalog")
def catalog(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return jobs.CATALOG


@router.get("/inventory")
def inventory(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return jobs.inventory()


@router.get("/capabilities")
def capabilities(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    items = []
    for cap_id, cls in sorted(MODELS.items()):
        items.append(
            {
                "id": cap_id,
                "capability_id": cap_id,
                "block_ids": list(jobs.CAPABILITY_BLOCKS.get(cap_id, [])),
                "fields": list(getattr(cls, "FIELDS", []) or []),
                "constraints": dict(getattr(cls, "CONSTRAINTS", {}) or {}),
                "money_fields": list(getattr(cls, "MONEY_FIELDS", []) or []),
                "entity": getattr(cls, "ENTITY", cap_id),
                "authority": dict(READ_AUTHORITY.get(cap_id) or {}),
                "http": {
                    "create": "POST /v1/%s" % cap_id,
                    "list": "GET /v1/%s" % cap_id,
                    "get": "GET /v1/%s/{id}" % cap_id,
                },
            }
        )
    return {"items": items}


@router.get("/gates")
def gates(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return jobs.GATES


@router.get("/provenance")
def provenance(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return jobs.provenance()


def _validate(cap_id: str, payload: Dict[str, Any]) -> None:
    reject_reserved_payload_keys(payload)
    reject_invalid_payload(cap_id, payload)
    reject_unknown_approver(cap_id, payload)


def _stored_record(cap_id: str, stored: Dict[str, Any]) -> Dict[str, Any]:
    return MODELS[cap_id].from_dict(stored).to_dict()


def _make_create(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    async def create(payload: Dict[str, Any], request: Request) -> Any:
        tenant = require_platform_token(request)
        _validate(cap_id, payload)
        token = bind_tenant(tenant.tenant_id)
        try:
            try:
                answer = _run(cap_id, payload)
            except Exception as exc:
                answer = _error(cap_id, exc)
        finally:
            release_tenant(token)
        if not isinstance(answer, dict):
            answer = {
                "ok": False,
                "capability": cap_id,
                "error": "handle() returned a non-mapping",
            }
        if answer.get("ok") is False:
            return answer
        columns = store.COLUMNS.get(entity, [])
        record = {k: v for k, v in payload.items() if k in columns}
        try:
            stored = store.save(entity, record, tenant.tenant_id)
        except Exception as exc:
            return _error(cap_id, exc)
        merged = dict(answer)
        merged.setdefault("ok", True)
        merged["capability"] = cap_id
        merged["stored"] = stored
        merged["record"] = _stored_record(cap_id, stored)
        merged["id"] = stored.get("id")
        merged["record_id"] = stored.get("id")
        return merged

    create.__name__ = "%s_create" % cap_id
    return create


def _make_list(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    def list_records(request: Request) -> Dict[str, Any]:
        tenant = require_read_token(request)
        allowed = set(store.COLUMNS.get(entity, [])) | set(LIST_CONTROLS)
        given = dict(request.query_params)
        unknown = sorted(k for k in given if k not in allowed)
        if unknown:
            raise HTTPException(
                status_code=422, detail="unknown query field(s): " + ", ".join(unknown)
            )
        try:
            limit = int(given.get("limit", 50))
            offset = int(given.get("offset", 0))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="limit/offset must be integers")
        try:
            return _labelled(
                cap_id,
                store.query(
                    entity,
                    tenant.tenant_id,
                    filters={k: v for k, v in given.items() if k not in LIST_CONTROLS},
                    sort=given.get("sort"),
                    order=given.get("order", "asc"),
                    limit=limit,
                    offset=offset,
                ),
            )
        except (store.QueryError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    list_records.__name__ = "%s_list" % cap_id
    return list_records


def _make_get(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    def get_record(item_id: int, request: Request) -> Dict[str, Any]:
        tenant = require_read_token(request)
        record = store.get(entity, item_id, tenant.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="not found")
        return _labelled(cap_id, record)

    get_record.__name__ = "%s_get" % cap_id
    return get_record


def _make_update(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    async def update_record(item_id: int, payload: Dict[str, Any], request: Request) -> Any:
        tenant = require_platform_token(request)
        existing = store.get(entity, item_id, tenant.tenant_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="not found")
        _validate(cap_id, payload)
        token = bind_tenant(tenant.tenant_id)
        try:
            try:
                answer = _run(cap_id, payload)
            except Exception as exc:
                answer = _error(cap_id, exc)
        finally:
            release_tenant(token)
        if isinstance(answer, dict) and answer.get("ok") is False:
            return answer
        columns = store.COLUMNS.get(entity, [])
        record = {k: v for k, v in payload.items() if k in columns}
        updated = store.update(entity, item_id, record, tenant.tenant_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="not found")
        merged = dict(answer) if isinstance(answer, dict) else {"ok": True}
        merged.setdefault("ok", True)
        merged["capability"] = cap_id
        merged["stored"] = updated
        merged["record"] = _stored_record(cap_id, updated)
        merged["id"] = updated.get("id")
        merged["record_id"] = updated.get("id")
        return merged

    update_record.__name__ = "%s_update" % cap_id
    return update_record


def _make_delete(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    def delete_record(item_id: int, request: Request) -> Dict[str, Any]:
        tenant = require_platform_token(request)
        existing = store.get(entity, item_id, tenant.tenant_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="not found")
        removed = store.delete(entity, item_id, tenant.tenant_id)
        return _labelled(cap_id, {"ok": bool(removed), "capability": cap_id, "id": item_id})

    delete_record.__name__ = "%s_delete" % cap_id
    return delete_record


for _cap_id in CAPABILITY_IDS:
    router.add_api_route(
        "/%s" % _cap_id, _make_create(_cap_id), methods=["POST"],
        name="%s_create" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    router.add_api_route(
        "/%s" % _cap_id, _make_list(_cap_id), methods=["GET"],
        name="%s_list" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_get(_cap_id), methods=["GET"],
        name="%s_get" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_update(_cap_id), methods=["PUT"],
        name="%s_update" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_delete(_cap_id), methods=["DELETE"],
        name="%s_delete" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
