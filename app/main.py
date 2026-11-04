"""The ASGI application.

Boot order is the contract: schema first (Alembic), then the locked block
check, then traffic. Health is the shipped ``app/health.py`` -- fail-closed on
process, disk, database and migration head -- and observability is mounted
once, so /metrics reports this process rather than the module existing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import __version__ as platform_version
from app import dispatch, health, observe, observability
from app.rag_routes import RAG
from app.routes import KERNEL, ROUTER

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

TITLE = "Cerebrum Executive Programs"
DESCRIPTION = (
    "A data-driven executive-education platform: 16-week tracks from validated "
    "YAML, AI faculty in six kernel modes, an independent memo grader, defenses, "
    "capstone review and graduation."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import migrations

    migrations.upgrade_head()
    dispatch.verify_locked_blocks()
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False


app = FastAPI(
    title=TITLE,
    description=DESCRIPTION,
    version=platform_version,
    lifespan=lifespan,
)

observe.install_observability(app)
observability.mount_observability(app)

app.include_router(KERNEL)
app.include_router(RAG)
app.include_router(ROUTER)


@app.get("/health", tags=["ops"])
def health_route():
    """The shipped fail-closed health body (process, disk, database, head)."""
    return health.health_response()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def console():
    """The operator console: app/static/index.html, the platform's one UI."""
    if INDEX_FILE.is_file():
        return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<!doctype html><html><body><h1>Cerebrum Executive Programs</h1>"
        "<p>The console asset is missing from this image.</p></body></html>",
        status_code=200,
    )


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
