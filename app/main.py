"""FastAPI application factory for Cerebrum Executive Programs."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import observability, track_schema
from app.health import health_response
from app.observe import install_observability
from app.rag_routes import router as rag_router
from app.routers.capabilities import router as capabilities_router
from app.routers.exports import router as exports_router
from app.routers.kernel import router as kernel_router
from app.version_info import VERSION

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _boot() -> None:
    storage = (os.getenv("STORAGE_PATH") or "").strip()
    if not storage:
        raise RuntimeError("STORAGE_PATH is not set; refusing to start without a persistent disk")
    root = Path(storage)
    root.mkdir(parents=True, exist_ok=True)
    from app.migrations import upgrade_head

    upgrade_head()
    # Tracks are loaded and validated at startup: an invalid file is a boot
    # refusal naming the offending field path, not a runtime surprise.
    try:
        track_schema.load_all()
    except track_schema.TrackError as exc:
        raise RuntimeError("track file refused at startup: %s" % exc) from exc


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _boot()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Cerebrum Executive Programs",
        version=VERSION,
        description=(
            "A data-driven executive-education platform: 16-week programmes "
            "defined entirely in validated YAML track files, a generated "
            "96-session calendar, faculty sessions in six kernel modes, "
            "rubric grading with provenance, a live gradebook and transcript, "
            "term defenses and a three-verdict capstone review."
        ),
        lifespan=lifespan,
    )
    install_observability(application)
    observability.install_metrics(application)
    # The kernel and retrieval routers are registered before the generic
    # capability routes so /v1/tracks, /v1/formulas and /v1/rag/* are not
    # swallowed by /v1/{capability_id}.
    application.include_router(kernel_router)
    application.include_router(rag_router)
    application.include_router(exports_router)
    application.include_router(capabilities_router)

    @application.get("/health")
    def health():
        return health_response()

    if STATIC_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @application.get("/", include_in_schema=False)
        def console():
            return FileResponse(str(STATIC_DIR / "index.html"))

    return application


app = create_app()
