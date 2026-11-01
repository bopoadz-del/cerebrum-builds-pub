"""The platform's HTTP surface: kernel roster + capability CRUD, one router.

``app/main.py`` mounts this at ``/v1``. The kernel routes are registered
first (a kernel name must never fall through to ``/{capability_id}``); the
capability routes after them. ``ROUTE_ENTITIES`` is re-exported here because
it is the declared answer to "which entity does this capability's route save
to" -- the migration, the handler's ENTITY and the one-record round-trip all
read the same name.

Every /v1 route is authenticated (401 with no token), every validation
failure is a 4xx naming the field, and only a declared vocabulary is
accepted. The ROUTE owns the tenant-scoped save: a handler never persists.
Tenancy is resolved from the bearer token, never from the payload.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.routers.capabilities import (
    CAPABILITY_IDS,
    ENTITY_OF,
    LIST_CONTROLS,
    READ_AUTHORITY,
    ROUTE_ENTITIES,
    capability_router,
)
from app.routers.kernel import kernel_router

router = APIRouter()
router.include_router(kernel_router)
router.include_router(capability_router)

__all__ = [
    "router",
    "ROUTE_ENTITIES",
    "CAPABILITY_IDS",
    "ENTITY_OF",
    "READ_AUTHORITY",
    "LIST_CONTROLS",
]
