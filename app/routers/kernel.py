"""Kernel job routes: the read-only roster each Factory kernel publishes.

Registered before the capability routes, so a kernel name (jobs, catalog,
inventory, gates, provenance, authority) can never be mistaken for a
capability id by the dynamic /{capability_id} route.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from fastapi import APIRouter, Request

from app import authority as authority_layer
from app.auth import require_read_token
from app.jobs import CATALOG, GATES, JOBS
from app.models import MODELS
from app.routers.capabilities import READ_AUTHORITY

kernel_router = APIRouter()

# --------------------------------------------------------------------------
# Kernel job routes (read-only)
# --------------------------------------------------------------------------
@kernel_router.get("/jobs")
def list_jobs(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return {"jobs": JOBS}


@kernel_router.get("/catalog")
def catalog(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return CATALOG


@kernel_router.get("/inventory")
def inventory(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    from app import jobs

    return jobs.inventory()


@kernel_router.get("/capabilities")
def capabilities(request: Request) -> Dict[str, Any]:
    """The roster, with each capability's own declared fields and rules.

    The console draws its forms from this answer, so the field list a form
    posts is the list the capability's model declares -- never a second,
    hand-kept contract in the page.
    """
    require_read_token(request)
    bindings = {}
    for entry in (CATALOG.get("bindings") or []):
        if isinstance(entry, dict) and entry.get("capability_id"):
            bindings[entry["capability_id"]] = entry

    items = []
    for cap_id, cls in sorted(MODELS.items()):
        binding = bindings.get(cap_id) or {}
        item = {
            "id": cap_id,
            "capability_id": cap_id,
            "block_ids": list(binding.get("block_ids") or []),
            "gap": bool(binding.get("gap")),
        }
        import typing as _typing

        item["fields"] = list(getattr(cls, "FIELDS", []) or [])
        item["field_types"] = {
            name: {int: "int", float: "float", bool: "bool"}.get(
                _typing.get_type_hints(cls).get(name, str), "str"
            )
            for name in item["fields"]
        }
        item["constraints"] = dict(getattr(cls, "CONSTRAINTS", {}) or {})
        item["money_fields"] = list(getattr(cls, "MONEY_FIELDS", []) or [])
        item["entity"] = getattr(cls, "ENTITY", cap_id)
        item["authority"] = dict(READ_AUTHORITY.get(cap_id) or {})
        item["http"] = {
            "create": "POST /v1/%s" % cap_id,
            "list": "GET /v1/%s" % cap_id,
            "get": "GET /v1/%s/{id}" % cap_id,
            "update": "PUT /v1/%s/{id}" % cap_id,
            "delete": "DELETE /v1/%s/{id}" % cap_id,
        }
        try:
            from app import placeholders

            item["placeholder"] = bool(placeholders.PLACEHOLDER_CONNECTORS.get(cap_id))
            item["placeholder_settings"] = [
                placeholders.setting_for(c)
                for c in (placeholders.PLACEHOLDER_CONNECTORS.get(cap_id) or [])
            ]
        except ImportError:
            item["placeholder"] = False
        items.append(item)
    return {
        "items": items,
        "authority": authority_layer.label("procedures", "app/routes.py#capabilities"),
    }


@kernel_router.get("/gates")
def gates(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    return GATES


@kernel_router.get("/provenance")
def provenance(request: Request) -> Dict[str, Any]:
    require_read_token(request)
    from app import jobs

    return jobs.provenance()


@kernel_router.get("/authority")
def authority_layers(request: Request) -> Dict[str, Any]:
    """precedence.v1 as data: the layers an answer's label indexes into."""
    require_read_token(request)
    from app import authority

    return authority.precedence_table()


