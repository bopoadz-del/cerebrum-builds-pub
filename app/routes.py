"""Router composition and the route -> entity map the gates read."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import MODELS
from app.routers import capabilities, platform, rag

ROUTE_ENTITIES = {capability_id: cls.ENTITY for capability_id, cls in MODELS.items()}

router = APIRouter()
# Static and retrieval routes come first: the dynamic /v1/{capability_id}
# surface must never shadow /v1/jobs, /v1/rag/query and friends.
router.include_router(platform.router)
router.include_router(rag.router)
router.include_router(capabilities.router)
