"""Route assembly and the entities each capability's route persists to."""

from __future__ import annotations

from fastapi import FastAPI

from app import jobs
from app.routers import capabilities as capability_routes
from app.routers import kernel as kernel_routes

#: capability id -> the store entity its route saves to. The harness reads
#: this to know what a POST must leave behind.
ROUTE_ENTITIES = dict(jobs.ROUTE_ENTITIES)


def install_routes(app: FastAPI) -> None:
    app.include_router(kernel_routes.router)
    app.include_router(capability_routes.router)
