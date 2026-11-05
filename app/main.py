"""Harbourline Civil Works contracts-administration platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import health, jobs, observe
from app.observability import mount_observability
from app.routers import capabilities
from app.routes import router as kernel_router

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.migrations import upgrade_head

    upgrade_head()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Harbourline Civil Works",
        description=(
            "Contracts administration for Harbourline Civil Works: progress claims, "
            "delay damages, QA/ITP records and the document register, grounded in the "
            "uploaded contract and BOQ."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    observe.install_observability(application)
    mount_observability(application)

    application.include_router(kernel_router)
    application.include_router(capabilities.router)

    @application.get("/health", tags=["ops"])
    def health_endpoint():
        return health.health_response()

    @application.get("/", include_in_schema=False)
    def console():
        index = STATIC_DIR / "index.html"
        if not index.is_file():
            return FileResponse(STATIC_DIR / "index.html", status_code=404)
        return FileResponse(index, media_type="text/html")

    @application.get("/static/{asset:path}", include_in_schema=False)
    def static_asset(asset: str):
        root = STATIC_DIR.resolve()
        target = (STATIC_DIR / asset).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            return FileResponse(root / "index.html", status_code=404)
        return FileResponse(target)

    return application


app = create_app()
