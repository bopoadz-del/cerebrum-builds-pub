"""HTTP routes over the capability actions.

The route owns authentication, validation and the tenant-scoped save.  A
handler never persists: it receives the caller's own fields, does the domain
work, and reports success or a typed refusal.
"""

from __future__ import annotations

import importlib
import json
import re
from contextlib import nullcontext
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import domain_rules, placeholders, store, tenancy
from app.action_common import minutes, split_list
from app.models import MODELS
from app.tenancy import Unauthorized, resolve_tenant

AUTH_ERROR = "unauthorized"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TITLES = {
    "customer_booking_flow": "Customer booking flow",
    "contractor_onboarding_and_service_areas": "Contractor onboarding and service areas",
    "contractor_availability_schedule": "Contractor availability schedule",
    "location_based_matching": "Location-based matching",
    "booking_status_lifecycle": "Booking status lifecycle",
    "booking_notifications": "Booking notifications",
    "invoicing_and_payouts": "Invoicing and payouts",
    "ops_back_office": "Ops back office",
    "audit": "Audit",
    "config": "Config",
    "email": "Email",
    "billing": "Billing",
}

ROUTE_ENTITIES: Dict[str, str] = {cap: cap for cap in MODELS}


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"ok": False, "error": AUTH_ERROR})


def _tenant_for(request: Request):
    try:
        return resolve_tenant(request.headers)
    except Unauthorized:
        return None


def _reject(field: str, reason: str, allowed: Optional[List[Any]] = None,
            message: str = "validation_failed") -> JSONResponse:
    body: Dict[str, Any] = {
        "ok": False,
        "error": message,
        "rejected_field": field,
        "rejection_reason": reason,
    }
    headers = {
        "X-Rejected-Field": json.dumps(field),
        "X-Rejection-Reason": reason,
    }
    if allowed is not None:
        body["allowed_values"] = allowed
        headers["X-Allowed-Values"] = json.dumps(allowed)
    return JSONResponse(status_code=422, content=body, headers=headers)


def _validate(capability_id: str, payload: Any) -> Optional[JSONResponse]:
    if not isinstance(payload, dict):
        return _reject("body", "not_an_object")
    if "action" in payload:
        return _reject("action", "reserved_field")
    model = MODELS[capability_id]
    for name in model.FIELDS:
        rules = model.CONSTRAINTS.get(name) or {}
        value = payload.get(name)
        required = bool(rules.get("required"))
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                return _reject(name, "missing_required")
            continue
        declared = rules.get("type", "str")
        if declared == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                return _reject(name, "wrong_type")
        elif declared in ("float", "money", "quantity"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return _reject(name, "wrong_type")
        elif declared == "bool":
            if not isinstance(value, bool):
                return _reject(name, "wrong_type")
        else:
            if not isinstance(value, str):
                return _reject(name, "wrong_type")
        allowed = rules.get("allowed_values")
        if allowed and value not in allowed:
            return _reject(name, "not_allowed", list(allowed))
        # Format metadata guides the sample builder (a declared time samples
        # as 10:00:00).  Shape is enforced by the handler's own domain rules;
        # the route refuses the wrong TYPE and any value outside a vocabulary.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            low, high = rules.get("min"), rules.get("max")
            if low is not None and value < low:
                return _reject(name, "below_minimum")
            if high is not None and value > high:
                return _reject(name, "above_maximum")
    return None


def _booking_conflict(tenant_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The same overlap rule the handler and the matching step read.

    A live booking holds a place; a contractor with capacity above one can
    take as many live bookings as the capacity allows.
    """
    contractor = str(payload.get("contractor_reference") or "")
    date = str(payload.get("booking_date") or "")
    start = domain_rules.minutes(payload.get("start_time"))
    end = domain_rules.minutes(payload.get("end_time"))
    if not contractor or not date or start is None:
        return None
    start, end, _ = domain_rules.shift_window(
        start, end, domain_rules.service_minutes()
    )
    token = tenancy.set_current_tenant(tenant_id)
    try:
        profile = domain_rules.contractor_profile(contractor)
        capacity = int((profile or {}).get("capacity") or 1)
        rows = domain_rules.overlapping_bookings(contractor, date, start, end)
    finally:
        tenancy.reset_current_tenant(token)
    # A booking holds its slot from the moment it is requested: requested,
    # accepted and in progress all count against capacity.  Only a completed
    # or cancelled (``closed``) booking releases it.
    if len(rows) >= max(1, capacity):
        return rows[0]
    return None


def _action_module(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


def _capability_meta(tenant_id: str = "") -> List[Dict[str, Any]]:
    out = []
    for capability_id, model in MODELS.items():
        fields = model.field_specs()
        properties = {}
        required = []
        for field in fields:
            spec = {key: value for key, value in field.items() if key != "name"}
            properties[field["name"]] = spec
            if (model.CONSTRAINTS.get(field["name"]) or {}).get("required"):
                required.append(field["name"])
        out.append({
            "id": capability_id,
            "capability_id": capability_id,
            "name": TITLES.get(capability_id, capability_id.replace("_", " ")),
            "entity": model.ENTITY,
            "tenant_id": tenant_id,
            "fields": fields,
            "input_schema": {"type": "object", "properties": properties, "required": required},
            "blocks": list(getattr(_action_module(capability_id), "BLOCK_IDS", []) or []),
        })
    return out


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/v1/jobs")
    async def jobs(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {
            "ok": True,
            "tenant_id": tenant.tenant_id,
            "jobs": [
                {"kernel": "COLLECTOR", "title": "Binding surveyor", "mandate": "Survey the brief and bind verified blocks", "http_routes": ["/v1/catalog"], "agent": "collector"},
                {"kernel": "CLONER", "title": "Block stocker", "mandate": "Vendor the locked block set", "http_routes": ["/v1/inventory"], "agent": "cloner"},
                {"kernel": "WRITER", "title": "Platform manufacturer", "mandate": "Author the platform to the brief", "http_routes": ["/v1/capabilities"], "agent": "writer"},
                {"kernel": "TESTER", "title": "Acceptance inspector", "mandate": "Grade the product against its acceptance floor", "http_routes": ["/v1/gates"], "agent": "tester"},
                {"kernel": "STORE_MANAGER", "title": "Store registrar", "mandate": "Register provenance and package the export", "http_routes": ["/v1/provenance"], "agent": "store_manager"},
            ],
        }

    @router.get("/v1/catalog")
    async def catalog(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {"ok": True, "tenant_id": tenant.tenant_id, "kernel": "COLLECTOR", "capabilities": list(MODELS), "blocks": sorted({b for m in MODELS.values() for b in getattr(_action_module(m.ENTITY), "BLOCK_IDS", [])})}

    @router.get("/v1/inventory")
    async def inventory(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {"ok": True, "tenant_id": tenant.tenant_id, "kernel": "CLONER", "lock": "blocks.lock.json", "blocks": sorted({b for m in MODELS.values() for b in getattr(_action_module(m.ENTITY), "BLOCK_IDS", [])})}

    @router.get("/v1/gates")
    async def gates(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {"ok": True, "tenant_id": tenant.tenant_id, "kernel": "TESTER", "runs_over_http": False, "gates": ["boot", "gates", "round_trip", "writer_behaviour"]}

    @router.get("/v1/provenance")
    async def provenance(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {"ok": True, "tenant_id": tenant.tenant_id, "kernel": "STORE_MANAGER", "provenance": "docs/provenance/provenance.json", "blocks": "blocks.lock.json"}

    @router.get("/v1/capabilities")
    async def capabilities(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        items = _capability_meta(tenant.tenant_id)
        return {
            "ok": True,
            "tenant_id": tenant.tenant_id,
            "tenant": {"id": tenant.tenant_id},
            "tenant_bound": True,
            "principal": {"kind": "bearer", "tenant_id": tenant.tenant_id},
            "items": items,
            "capabilities": items,
        }

    @router.get("/v1/tenant")
    async def tenant_identity(request: Request):
        """The authenticated principal's tenant, as the console binds it."""
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        return {
            "ok": True,
            "tenant_id": tenant.tenant_id,
            "tenant": {"id": tenant.tenant_id},
            "principal": {"kind": "bearer", "tenant_id": tenant.tenant_id},
        }

    @router.get("/v1/whoami")
    async def whoami(request: Request):
        return await tenant_identity(request)

    @router.post("/v1/{capability_id}")
    async def create_capability(capability_id: str, request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        if capability_id not in MODELS:
            return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
        if placeholders.PLACEHOLDER_CONNECTORS.get(capability_id):
            return JSONResponse(status_code=503, content=placeholders.refusal(capability_id))
        try:
            payload = await request.json()
        except Exception:
            return _reject("body", "invalid_json")
        refusal = _validate(capability_id, payload)
        if refusal is not None:
            return refusal
        # A retry with the same reference is the same record, not a new one:
        # the caller's own idempotency key.  Return what was stored -- except
        # for a contractor profile, where the same reference is the contractor
        # updating their own account, so the new declaration replaces it.
        reference = str(payload.get("reference") or "").strip()
        existing_row = None
        if reference:
            try:
                stored = store.list_all(capability_id, tenant.tenant_id)
            except Exception:
                stored = []
            for row in stored:
                if str(row.get("reference") or "") != reference:
                    continue
                if capability_id == "contractor_onboarding_and_service_areas":
                    existing_row = row
                    break
                model = MODELS[capability_id]
                record = model.from_dict(row).to_dict()
                return {
                    "ok": True,
                    "record": record,
                    "stored": record,
                    "id": record.get("id"),
                    "result": {"idempotent": True, "reference": reference},
                    "blocks": list(getattr(_action_module(capability_id), "BLOCK_IDS", []) or []),
                }
        guard = store.guard_writes() if capability_id == "customer_booking_flow" else nullcontext()
        module = _action_module(capability_id)
        token = tenancy.set_current_tenant(tenant.tenant_id)
        try:
            with guard:
                if capability_id == "customer_booking_flow":
                    conflict = _booking_conflict(tenant.tenant_id, payload)
                    if conflict is not None:
                        return JSONResponse(status_code=409, content={
                            "ok": False,
                            "error": "contractor already has a booking in that slot",
                            "error_kind": "conflict",
                            "conflicting_id": conflict.get("id"),
                        })
                outcome = module.handle(payload)
                if not isinstance(outcome, dict):
                    outcome = {"ok": False, "error": "handler returned a non-mapping"}
                if outcome.get("ok") is False:
                    return JSONResponse(status_code=200, content=outcome)
                # The route persists the request.  Where the handler computed
                # values the entity must carry (a durable audit chain link, or
                # the catalogue-approved subset of a contractor's selection),
                # they are written onto the record here -- never invented by
                # the handler's own store call (handlers have no tenant).
                result = outcome.get("result") or {}
                if capability_id == "audit":
                    for key in ("sequence", "previous_digest", "chain_digest"):
                        payload[key] = result.get(key)
                elif capability_id == "contractor_onboarding_and_service_areas":
                    payload["service_suburbs"] = ", ".join(result.get("service_areas") or [])
                    payload["pending_suburbs"] = ", ".join(result.get("pending_areas") or [])
                    payload["retired_suburbs"] = ", ".join(result.get("retired_areas") or [])
                    payload["catalogue_state"] = result.get("onboarding_state")
                    payload["active"] = bool(result.get("activated"))
                try:
                    if existing_row is not None:
                        saved = store.update(capability_id, int(existing_row["id"]),
                                             payload, tenant.tenant_id)
                    else:
                        saved = store.save(capability_id, payload, tenant.tenant_id)
                except Exception as exc:
                    return JSONResponse(status_code=503, content={
                        "ok": False,
                        "error": "persistence unavailable: %s" % type(exc).__name__,
                        "error_kind": "unavailable",
                    })
        finally:
            tenancy.reset_current_tenant(token)
        result = outcome.get("result") or {}
        if (
            capability_id == "booking_status_lifecycle"
            and result.get("allowed") is True
            and result.get("booking_reference")
        ):
            state_map = {"requested": "open", "accepted": "in_progress",
                         "in_progress": "in_progress", "completed": "closed",
                         "cancelled": "closed"}
            new_status = state_map.get(str(result.get("to_state") or ""))
            if new_status:
                try:
                    rows = store.list_all("customer_booking_flow", tenant.tenant_id)
                except Exception:
                    rows = []
                for row in rows:
                    if str(row.get("reference") or "") == str(result["booking_reference"]):
                        store.update("customer_booking_flow", int(row["id"]),
                                     {"status": new_status}, tenant.tenant_id)
                        break
        if capability_id == "ops_back_office" and result.get("catalogue_entry"):
            entry = dict(result["catalogue_entry"])
            try:
                catalogue = store.list_all("service_suburb", tenant.tenant_id)
            except Exception:
                catalogue = []
            existing = next(
                (row for row in catalogue
                 if str(row.get("reference") or "") == str(entry.get("reference") or "")),
                None,
            )
            if existing is not None:
                store.update("service_suburb", int(existing["id"]), entry, tenant.tenant_id)
            else:
                store.save("service_suburb", entry, tenant.tenant_id)
        model = MODELS[capability_id]
        record = model.from_dict(saved).to_dict()
        body = {
            "ok": True,
            "record": record,
            "stored": record,
            "id": record.get("id"),
            "result": outcome.get("result") or {},
            "blocks": list(getattr(module, "BLOCK_IDS", []) or []),
        }
        return body

    @router.get("/v1/{capability_id}")
    async def list_capability(capability_id: str, request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        if capability_id not in MODELS:
            return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
        try:
            rows = store.list_all(capability_id, tenant.tenant_id)
        except Exception:
            return {"ok": True, "items": [], "total": 0, "migrated": False}
        model = MODELS[capability_id]
        items = [model.from_dict(row).to_dict() for row in rows]
        return {"ok": True, "items": items, "total": len(items), "migrated": True}

    @router.get("/v1/customer_booking_flow/available")
    async def available_contractors(request: Request, suburb: str = "", booking_date: str = "",
                                    start_time: str = "", end_time: str = ""):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        wanted = domain_rules.normalise_area(suburb)
        weekday = domain_rules.weekday_of(booking_date) if booking_date else ""
        if booking_date and weekday is None:
            return _reject("booking_date", "wrong_format")
        start = domain_rules.minutes(start_time)
        end = domain_rules.minutes(end_time)
        window = None
        if start is not None:
            window = domain_rules.shift_window(start, end, domain_rules.service_minutes())
        token = tenancy.set_current_tenant(tenant.tenant_id)
        try:
            contractors = store.list_all("contractor_onboarding_and_service_areas", tenant.tenant_id)
            schedules = store.list_all("contractor_availability_schedule", tenant.tenant_id)
            bookings = store.list_all("customer_booking_flow", tenant.tenant_id)
        except Exception:
            contractors, schedules, bookings = [], [], []
        finally:
            tenancy.reset_current_tenant(token)
        items = []
        token = tenancy.set_current_tenant(tenant.tenant_id)
        try:
            for contractor in contractors:
                ref = str(contractor.get("reference") or "")
                if not ref:
                    continue
                areas = domain_rules.contractor_service_areas(contractor)
                if wanted and wanted not in {domain_rules.normalise_area(a) for a in areas}:
                    continue
                if not domain_rules.truthy(contractor.get("active"), default=True):
                    continue
                capacity = int(contractor.get("capacity") or 1)
                covered = None
                slots = []
                if weekday:
                    if window is not None:
                        covered = domain_rules.schedule_covers(ref, weekday, window[0], window[1])
                    slots = domain_rules.contractor_open_slots(ref, weekday, booking_date)
                if window is not None:
                    if covered is not True:
                        continue
                    slots = [slot for slot in slots
                             if slot.get("available")
                             and slot["start_minute"] >= window[0]
                             and slot["end_minute"] <= window[1]]
                    if not slots:
                        continue
                windows = [
                    {"weekday": row.get("weekday"),
                     "start_time": row.get("start_time"),
                     "end_time": row.get("end_time"),
                     "capacity": int(row.get("capacity") or capacity),
                     "crosses_midnight": domain_rules.shift_window(
                         domain_rules.minutes(row.get("start_time")) or 0,
                         domain_rules.minutes(row.get("end_time")),
                         domain_rules.DAY_MINUTES,
                     )[2]}
                    for row in domain_rules.contractor_schedule(ref, weekday)
                ]
                items.append({
                    "contractor_reference": ref,
                    "contractor_name": contractor.get("contractor_name"),
                    "service_suburbs": areas,
                    "vehicle_type": contractor.get("vehicle_type"),
                    "capacity": capacity,
                    "schedule_checked": covered is not None,
                    "availability": windows,
                    "open_slots": slots,
                    "open_slot_count": len(slots),
                    "available": True,
                })
        finally:
            tenancy.reset_current_tenant(token)
        items.sort(key=lambda item: (-item["open_slot_count"], item["contractor_reference"]))
        return {"ok": True, "items": items, "total": len(items), "suburb": suburb,
                "weekday": weekday or None}

    def _suburb_rows(tenant_id: str):
        token = tenancy.set_current_tenant(tenant_id)
        try:
            catalogue = store.list_all("service_suburb", tenant_id)
            contractors = store.list_all("contractor_onboarding_and_service_areas", tenant_id)
        finally:
            tenancy.reset_current_tenant(token)
        proposals = []
        seen = set()
        for row in contractors:
            pending = domain_rules.split_areas(row.get("pending_suburbs"))
            for area in pending:
                key = domain_rules.normalise_area(area)
                if key and key not in seen:
                    seen.add(key)
                    proposals.append({
                        "suburb": area,
                        "contractor_reference": row.get("reference"),
                        "catalogue_state": row.get("catalogue_state"),
                    })
        return catalogue, proposals

    @router.get("/v1/ops_back_office/suburbs")
    async def list_suburbs(request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        catalogue, proposals = _suburb_rows(tenant.tenant_id)
        active = [row for row in catalogue
                  if domain_rules.truthy(row.get("active"), default=True)]
        return {
            "ok": True,
            "tenant_id": tenant.tenant_id,
            "items": catalogue,
            "catalogue": active,
            "total": len(catalogue),
            "proposals": proposals,
        }

    @router.post("/v1/ops_back_office/suburbs")
    async def maintain_suburb(request: Request):
        """Ops adds, renames or retires a suburb in the managed catalogue."""
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        try:
            body = await request.json()
        except Exception:
            return _reject("body", "invalid_json")
        if not isinstance(body, dict):
            return _reject("body", "not_an_object")
        suburb = " ".join(str(body.get("suburb") or "").split())
        if not suburb:
            return _reject("suburb", "missing_required")
        if len(suburb) > 120:
            return _reject("suburb", "too_long")
        active = domain_rules.truthy(body.get("active"), default=True)
        region = " ".join(str(body.get("region") or "").split()) or None
        reference = "suburb:" + domain_rules.normalise_area(suburb)
        entry = {
            "reference": reference,
            "status": "open" if active else "closed",
            "notes": str(body.get("notes") or ""),
            "suburb": suburb,
            "region": region,
            "active": bool(active),
        }
        token = tenancy.set_current_tenant(tenant.tenant_id)
        try:
            existing = next(
                (row for row in store.list_all("service_suburb", tenant.tenant_id)
                 if str(row.get("reference") or "") == reference),
                None,
            )
            if existing is not None:
                saved = store.update("service_suburb", int(existing["id"]), entry,
                                     tenant.tenant_id)
            else:
                saved = store.save("service_suburb", entry, tenant.tenant_id)
            catalogue = store.list_all("service_suburb", tenant.tenant_id)
        finally:
            tenancy.reset_current_tenant(token)
        return {
            "ok": True,
            "record": saved,
            "id": saved.get("id") if saved else None,
            "items": catalogue,
            "catalogue": [row for row in catalogue
                          if domain_rules.truthy(row.get("active"), default=True)],
        }

    @router.get("/v1/{capability_id}/{record_id}")
    async def get_capability(capability_id: str, record_id: str, request: Request):
        tenant = _tenant_for(request)
        if tenant is None:
            return _unauthorized()
        if capability_id not in MODELS:
            return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
        try:
            numeric = int(record_id)
        except (TypeError, ValueError):
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
        row = store.get(capability_id, numeric, tenant.tenant_id)
        if row is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
        model = MODELS[capability_id]
        return {"ok": True, "record": model.from_dict(row).to_dict(), "id": numeric}

    return router
