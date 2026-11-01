"""Entrypoint for the coffee-compost factory platform.

Runs standalone: ``uvicorn app.main:app``. No factory, no block store, no
outbound dependency at runtime -- the vendored blocks are imported and run
in-process (app/dispatch.py).

Kernel jobs are at ``GET /v1/jobs``. ``GET /health`` is fail-closed
(process, disk, database, Alembic head). ``GET /metrics`` is mounted once by
app.observability. The one console is served at ``/`` from app/static.

Written by the factory WRITER role (codewhale exec).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from app.health import health_response
from app.observe import install_observability
from app.routes import router

logger = logging.getLogger(__name__)

PRODUCT_NAME = "Coffee-compost factory operations"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Settings the process cannot run without are validated once, by name:
    # a missing PLATFORM_TOKEN or PLATFORM_TAX_RATE fails here, not inside a
    # request at three in the morning.
    from app.settings import boot_settings

    boot_settings()
    # Fail-closed: a revision behind head refuses boot.
    from app.migrations import upgrade_head
    from app.observe import configure_logging

    upgrade_head()
    try:
        from app.preconditions import ensure_all

        ensure_all()
    except Exception:  # noqa: BLE001 - boot reports, it does not die here
        logger.exception("platform preconditions did not run")
    configure_logging()
    yield


app = FastAPI(title=PRODUCT_NAME, lifespan=lifespan)
install_observability(app)
try:
    from app.observability import mount_observability
except ImportError:  # pragma: no cover - factory substrate
    mount_observability = None
if mount_observability is not None:
    mount_observability(app)
app.include_router(router, prefix="/v1")


@app.exception_handler(Exception)
async def _sanitised_error(_request, exc: Exception):
    """An unhandled failure answers with its class, never with a secret."""
    from fastapi.responses import JSONResponse

    from app.security import sanitise_error

    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": sanitise_error("%s" % type(exc).__name__)},
    )


@app.get("/", include_in_schema=False)
def ui_root():
    here = Path(__file__).resolve().parent
    for candidate in (here / "static" / "index.html", here.parent / "frontend" / "index.html"):
        if candidate.is_file():
            return FileResponse(candidate, media_type="text/html")
    return HTMLResponse(
        "<!doctype html><html><body><h1>%s</h1></body></html>" % PRODUCT_NAME
    )


@app.get("/health")
def health():
    return health_response()
