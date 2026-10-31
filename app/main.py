"""FastAPI application factory for the car manufacturing platform."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import observe
from app import health as _health
from app.jobs import CAPABILITIES, JOBS
from app import money_settings
from app.migrations import current_revision, head_revision, upgrade_head
from app.rag_routes import router as rag_router
from app.routes import router as capability_router

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

_METRICS: Dict[str, float] = {"requests": 0.0, "total_seconds": 0.0, "max_seconds": 0.0}


def create_app() -> FastAPI:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        import os

        storage = os.getenv("STORAGE_PATH")
        if storage:
            Path(storage).mkdir(parents=True, exist_ok=True)
        upgrade_head()
        yield

    app = FastAPI(
        title="Electric car manufacturing platform",
        version="1.0.0",
        description="Manager-only money and document reasoning for two Moroccan EV plants.",
        lifespan=lifespan,
    )
    observe.install_observability(app)

    @app.middleware("http")
    async def _count(request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        _METRICS["requests"] += 1
        _METRICS["total_seconds"] += elapsed
        _METRICS["max_seconds"] = max(_METRICS["max_seconds"], elapsed)
        return response

    app.include_router(capability_router)
    app.include_router(rag_router)

    @app.get("/health")
    def health():
        return _health.health_response()

    @app.get("/metrics")
    def metrics():
        count = int(_METRICS["requests"])
        total = _METRICS["total_seconds"]
        average = (total / count) if count else 0.0
        body = "\n".join(
            [
                "# HELP platform_requests_total Requests served by this process.",
                "# TYPE platform_requests_total counter",
                f"platform_requests_total {count}",
                "# HELP platform_request_latency_seconds Request latency.",
                "# TYPE platform_request_latency_seconds gauge",
                f"platform_request_latency_seconds_avg {average:.6f}",
                f"platform_request_latency_seconds_max {_METRICS['max_seconds']:.6f}",
                "",
            ]
        )
        return PlainTextResponse(body, media_type="text/plain; version=0.0.4")

    @app.get("/v1/jobs")
    def jobs():
        return {"kernel": "WRITER", "jobs": JOBS}

    @app.get("/v1/catalog")
    def catalog():
        return {"kernel": "COLLECTOR", "items": CAPABILITIES}

    @app.get("/v1/inventory")
    def inventory():
        return {
            "kernel": "CLONER",
            "lock": "blocks.lock.json",
            "blocks": sorted({block for row in CAPABILITIES for block in row["blocks"]}),
        }

    @app.get("/v1/capabilities")
    def capabilities():
        return {
            "kernel": "WRITER",
            "items": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "entity": row["entity"],
                    "blocks": row["blocks"],
                }
                for row in CAPABILITIES
            ],
        }

    @app.get("/v1/gates")
    def gates():
        return {
            "kernel": "TESTER",
            "runs_over_http": False,
            "gates": ["code", "product", "store"],
            "revision": current_revision(),
            "head": head_revision(),
        }

    @app.get("/v1/provenance")
    def provenance():
        return {
            "kernel": "STORE_MANAGER",
            "product_id": "product",
            "country": money_settings.country(),
            "currency": money_settings.currency(),
            "capabilities": [row["id"] for row in CAPABILITIES],
        }

    @app.get("/", response_class=HTMLResponse)
    def console():
        index = STATIC / "index.html"
        if index.is_file():
            return HTMLResponse(index.read_text(encoding="utf-8"))
        return HTMLResponse("<html><body><h1>Console unavailable</h1></body></html>", status_code=500)

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    return app


app = create_app()
