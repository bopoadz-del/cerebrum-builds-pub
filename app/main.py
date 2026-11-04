"""FastAPI application factory and the served console."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import health, observe
from app.observability import mount_observability
from app.routes import router

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.migrations import upgrade_head

    upgrade_head()
    yield


app = FastAPI(
    title="Harbourline Civil Works Contracts Administration",
    version="1.0.0",
    lifespan=lifespan,
)

observe.install_observability(app)
mount_observability(app)

app.include_router(router)


@app.get("/health")
def health_endpoint():
    return health.health_response()


@app.get("/", include_in_schema=False)
def index():
    page = STATIC / "index.html"
    if not page.is_file():
        return JSONResponse(status_code=503, content={"ok": False, "error": "console not built"})
    return FileResponse(str(page), media_type="text/html")


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
