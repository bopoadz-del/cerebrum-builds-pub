"""The platform's ASGI app: health, metrics, the console and the API.

Boot applies the alembic head (which is what puts the SQLite file in WAL) and
the health probe asks app.db which database is live, so a Postgres
deployment and a SQLite one report their own truth.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse

from app import db as app_db
from app import dispatch, health, metrics, migrations, observe, routes

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    dispatch.verify_locked_blocks()
    migrations.upgrade_head()
    yield


app = FastAPI(
    title="Harbourline Civil Works Contracts Administration Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(metrics.MetricsMiddleware)
observe.install_observability(app)
routes.install_routes(app)

if STATIC_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def console():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    return PlainTextResponse(
        "The console has not been built into this image.", status_code=503
    )


@app.get("/health")
async def health_route():
    return health.health_response()


@app.get("/metrics", include_in_schema=False)
async def metrics_route():
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


@app.get("/meta", include_in_schema=False)
async def meta():
    return {
        "ok": True,
        "product": "Harbourline Civil Works Contracts Administration Platform",
        "backend": app_db.backend_name(),
        "capabilities": list(routes.ROUTE_ENTITIES),
    }
