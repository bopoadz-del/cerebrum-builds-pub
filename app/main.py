"""Harbourline Civil Works contracts administration -- application entry.

Boot order: migrations reach head, locked blocks (when the vendored tree is
present) are checked at their declared paths, then the routes serve. /health
is the shipped fail-closed probe and is never reimplemented here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from app import dispatch, health, migrations
from app.observability import mount_observability
from app.routes import router

STATIC = Path(__file__).resolve().parent / "static"


def verify_locked_blocks() -> None:
    """A locked block absent from its path is an error, never a fallback."""
    vendor = Path(__file__).resolve().parents[1] / "vendor" / "blocks"
    if not vendor.is_dir():
        return
    missing = [
        block_id for block_id, rel in dispatch.LOCKED_BLOCKS.items()
        if not (Path(__file__).resolve().parents[1] / rel).is_file()
    ]
    if missing:
        raise RuntimeError("locked blocks absent from their declared paths: " + ", ".join(sorted(missing)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrations.upgrade_head()
    verify_locked_blocks()
    yield


app = FastAPI(
    title="Harbourline Civil Works contracts administration",
    version="1.0.0",
    lifespan=lifespan,
)
mount_observability(app)
app.include_router(router)


@app.get("/health")
def health_route():
    return health.health_response()


@app.get("/")
def index():
    page = STATIC / "index.html"
    if not page.is_file():
        return JSONResponse(status_code=404, content={"ok": False, "error": "UI not built"})
    return FileResponse(page, media_type="text/html")
