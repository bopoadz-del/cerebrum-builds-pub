"""FastAPI application factory for the Harbourline contracts platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import health, migrations, observe, observability
from app.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    migrations.upgrade_head()
    yield


app = FastAPI(
    title="Harbourline Contracts Administration",
    version="1.0.0",
    description=(
        "Progress claims, delay damages, QA/ITP records, a document register and "
        "clause-grounded answers over the Harbourline Civil Works contract and BOQ."
    ),
    lifespan=lifespan,
)

observe.install_observability(app)
observability.mount_observability(app)
app.include_router(router)


@app.get("/health")
async def health_check():
    return health.health_response()


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="console")
