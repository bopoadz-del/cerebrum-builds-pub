"""The platform's route table (imported by probes for ROUTE_ENTITIES)."""

from __future__ import annotations

from app.rag_routes import router as rag_router
from app.routers.capabilities import ROUTE_ENTITIES, router as capabilities_router
from app.routers.exports import router as exports_router
from app.routers.kernel import router as kernel_router

__all__ = [
    "ROUTE_ENTITIES",
    "capabilities_router",
    "exports_router",
    "kernel_router",
    "rag_router",
]
