"""Capability CRUD routes: the router the six capabilities answer on.

Written by the factory WRITER role (codewhale exec).

Every /v1 route is authenticated (401 with no token), every validation
failure is a 4xx naming the field, and only a declared vocabulary is
accepted.  The ROUTE owns the tenant-scoped save: a handler never persists.
Tenancy is resolved from the bearer token, never from the payload.  A
capability whose connector is a declared placeholder answers the typed 503
refusal before validation and before its handler runs; nothing is stored.

Reads answer with the capability's authority label, so an operator (and the
console) can see which layer of precedence.v1 answered.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app import store
from app.auth import (
    reject_approvers,
    reject_invalid_payload,
    reject_reserved_payload_keys,
    require_platform_token,
    require_read_token,
)
from app.edge import reject_wrong_types
from app.models import MODELS
from app.tenancy import bind_tenant, release_tenant

capability_router = APIRouter()

#: The capability roster is app.models.MODELS -- the platform's own single
#: declaration (entity name == capability id).
CAPABILITY_IDS = sorted(MODELS)
#: The store entity each capability's route saves to.  The one-record
#: round-trip probe reads this back, so it names the migration's table.
ENTITY_OF = {cap: getattr(cls, "ENTITY", cap) for cap, cls in sorted(MODELS.items())}
ROUTE_ENTITIES = dict(ENTITY_OF)

#: The authority layer each capability's answers carry -- the same label its
#: handler stamps on a POST answer.  A READ answer is the platform's record
#: of that capability, so it answers at the same layer.
READ_AUTHORITY: Dict[str, Dict[str, Any]] = {}

for _cap in CAPABILITY_IDS:
    try:
        _mod = importlib.import_module("app.actions." + _cap)
        READ_AUTHORITY[_cap] = dict(getattr(_mod, "AUTHORITY"))
    except Exception:  # a capability that cannot import has no label
        READ_AUTHORITY[_cap] = {"layer": 3, "name": "formulas", "source": "app/actions/%s.py" % _cap}
#: Query parameters a list route understands beside the declared columns.
LIST_CONTROLS = ("limit", "offset", "sort", "order")


def _require_identity(request: Request) -> None:
    """Resolve the caller's tenant as a DEPENDENCY, before anything else.

    FastAPI validates a route's typed body and path parameters in the same
    pass as its dependencies, but sub-dependencies are solved first: making
    the token check a dependency means an anonymous caller gets 401 even
    when the body is not an object or the id is not a number, instead of a
    422 that confirms the route exists.
    """
    require_platform_token(request)


def _placeholder_refusal(cap_id: str) -> Optional[Dict[str, Any]]:
    """The typed 503 for a capability whose connector is a declared placeholder."""
    try:
        from app import placeholders
    except ImportError:
        return None
    return placeholders.refusal_for(cap_id)


def _run(cap_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    module = importlib.import_module("app.actions." + cap_id)
    return module.handle(payload)


def _labelled(capability_id: str, body: Any) -> Any:
    """Attach the capability's authority label to one read answer."""
    if not isinstance(body, dict):
        return body
    out = dict(body)
    label = READ_AUTHORITY.get(str(capability_id))
    if label is not None and "authority" not in out:
        out["authority"] = dict(label)
    return out


def _error(cap_id: str, exc: Exception) -> Dict[str, Any]:
    """A failed call as a refusal, with the class named and no secret in it.

    The message goes through app.security.sanitise_error: a driver or store
    exception can carry a filesystem path or a connection string, and an
    error body must never be the place that leaves the box.
    """
    from app.security import sanitise_error

    return {
        "ok": False,
        "capability": cap_id,
        "error": "%s: %s" % (type(exc).__name__, sanitise_error(str(exc))),
    }


# --------------------------------------------------------------------------
# Capability CRUD.  One set of handlers per capability, registered on the
# router by name at import; every write is tenant-scoped from the bearer
# token and every refusal is 4xx or ok:false with a reason, never a 500.
# --------------------------------------------------------------------------
def _validate(cap_id: str, payload: Dict[str, Any]) -> None:
    """Every edge check a write runs, in one place: reserved keys, the
    declared fields, the declared types, and the approval fields."""
    reject_reserved_payload_keys(payload)
    reject_invalid_payload(cap_id, payload)
    reject_wrong_types(cap_id, payload)
    reject_approvers(cap_id, payload)


def _derived_reading(
    cap_id: str, payload: Dict[str, Any], tenant_id: str
) -> Dict[str, Any]:
    """Fill the fields a capability declares as MEASURED, not typed.

    The capability's own model says which of its fields are a reading of the
    platform's records (``AGGREGATES``) and which entity and column values
    make a row part of the reading. This runs after the caller's payload has
    been validated -- so an out-of-range number the caller sent is still
    refused -- and before the handler sees it, because a handler has no
    tenant and must not reach the store itself. Tenancy comes from the
    authenticated principal, exactly as the save does.

    A capability that declares no aggregation is returned unchanged.
    """
    cls = MODELS.get(cap_id)
    declared = getattr(cls, "AGGREGATES", None)
    if not isinstance(declared, dict) or not declared:
        return payload
    entity = ENTITY_OF.get(cap_id, cap_id)
    measured = dict(payload)
    for field, rule in sorted(declared.items()):
        if not isinstance(rule, dict) or field not in store.COLUMNS.get(entity, []):
            continue
        source = str(rule.get("entity") or cap_id)
        try:
            if isinstance(rule.get("sum"), dict):
                summation = rule["sum"]
                measured[field] = store.total(
                    source,
                    tenant_id,
                    str(summation.get("column") or ""),
                    multiply_by=summation.get("multiply_by"),
                    filters=rule.get("filters"),
                    any_of=rule.get("any_of"),
                )
            else:
                measured[field] = store.count(
                    source,
                    tenant_id,
                    filters=rule.get("filters"),
                    any_of=rule.get("any_of"),
                )
        except Exception:  # an unreadable table leaves the reading as typed
            continue
    return measured


def _make_create(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    async def create(payload: Dict[str, Any], request: Request) -> Any:
        tenant = require_platform_token(request)
        refusal = _placeholder_refusal(cap_id)
        if refusal is not None:
            return JSONResponse(status_code=503, content=refusal)
        _validate(cap_id, payload)
        payload = _derived_reading(cap_id, payload, tenant.tenant_id)
        token = bind_tenant(tenant.tenant_id)
        try:
            try:
                answer = _run(cap_id, payload)
            except Exception as exc:  # a handler refusal is an answer, not a 500
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
        except Exception as exc:  # a store refusal is a refusal, not a 500
            return _error(cap_id, exc)
        merged = dict(answer)
        merged.setdefault("ok", True)
        merged["capability"] = cap_id
        merged["stored"] = stored
        merged["record"] = stored
        #: The record's own id at the top level: a reader (and the factory's
        #: round-trip probe) must not have to search the block evidence below
        #: for the id of the row the route just persisted.
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
                    entity, tenant.tenant_id,
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
            # A record belonging to another tenant is invisible: 404, never
            # 403 and never the record.
            raise HTTPException(status_code=404, detail="not found")
        return _labelled(cap_id, record)

    get_record.__name__ = "%s_get" % cap_id
    return get_record


def _make_update(cap_id: str) -> Callable[..., Any]:
    entity = ENTITY_OF[cap_id]

    async def update_record(item_id: int, payload: Dict[str, Any], request: Request) -> Any:
        tenant = require_platform_token(request)
        # Ownership first: another tenant's id (or one that does not exist)
        # reads as 404 here exactly as it does on GET and DELETE, even for a
        # capability whose connector is a placeholder.
        existing = store.get(entity, item_id, tenant.tenant_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="not found")
        refusal = _placeholder_refusal(cap_id)
        if refusal is not None:
            return JSONResponse(status_code=503, content=refusal)
        _validate(cap_id, payload)
        columns = store.COLUMNS.get(entity, [])
        # A PUT replaces the record, not only the columns the caller chose to
        # name: start from what is stored and overlay the validated payload.
        # Writing only the supplied keys would NULL every other column --
        # erasing the access_state/approved_by of an approved revocation and
        # silently dropping a payment_state out of the dashboard reading.
        record = {name: existing.get(name) for name in columns}
        record.update({k: v for k, v in payload.items() if k in columns})
        record = _derived_reading(cap_id, record, tenant.tenant_id)
        # The approval a write performs is decided by the RESULTING record,
        # so a PUT that leaves a revocation in place must still name an
        # approved principal.
        reject_approvers(cap_id, record)
        token = bind_tenant(tenant.tenant_id)
        try:
            try:
                answer = _run(cap_id, record)
            except Exception as exc:
                answer = _error(cap_id, exc)
        finally:
            release_tenant(token)
        if isinstance(answer, dict) and answer.get("ok") is False:
            return answer
        updated = store.update(entity, item_id, record, tenant.tenant_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="not found")
        merged = dict(answer) if isinstance(answer, dict) else {"ok": True}
        merged.setdefault("ok", True)
        merged["capability"] = cap_id
        merged["stored"] = updated
        merged["record"] = updated
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
    capability_router.add_api_route(
        "/%s" % _cap_id, _make_create(_cap_id), methods=["POST"],
        name="%s_create" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    capability_router.add_api_route(
        "/%s" % _cap_id, _make_list(_cap_id), methods=["GET"],
        name="%s_list" % _cap_id,
        dependencies=[Depends(_require_identity)],
    )
    capability_router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_get(_cap_id), methods=["GET"],
        name="%s_get" % _cap_id,
        dependencies=[Depends(_require_identity)],
    )
    capability_router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_update(_cap_id), methods=["PUT"],
        name="%s_update" % _cap_id, response_model=None,
        dependencies=[Depends(_require_identity)],
    )
    capability_router.add_api_route(
        "/%s/{item_id}" % _cap_id, _make_delete(_cap_id), methods=["DELETE"],
        name="%s_delete" % _cap_id,
        dependencies=[Depends(_require_identity)],
    )
