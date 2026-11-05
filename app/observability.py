"""Request metrics exposed at /metrics.

Mounted once in app.main; the counter is process-local and deliberately small.
"""

from __future__ import annotations

import threading
import time
from typing import Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_LOCK = threading.Lock()
_METRICS: Dict[str, float] = {
    "requests_total": 0,
    "latency_seconds_total": 0.0,
    "latency_seconds_max": 0.0,
}


class _MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        elapsed = max(0.0, time.monotonic() - started)
        with _LOCK:
            _METRICS["requests_total"] += 1
            _METRICS["latency_seconds_total"] += elapsed
            _METRICS["latency_seconds_max"] = max(_METRICS["latency_seconds_max"], elapsed)
        return response


def snapshot() -> dict:
    with _LOCK:
        total = int(_METRICS["requests_total"])
        seconds = float(_METRICS["latency_seconds_total"])
        return {
            "requests_total": total,
            "latency_seconds_total": round(seconds, 6),
            "latency_seconds_avg": round(seconds / total, 6) if total else 0.0,
            "latency_seconds_max": round(float(_METRICS["latency_seconds_max"]), 6),
        }


def mount_observability(app) -> None:
    app.add_middleware(_MetricsMiddleware)

    @app.get("/metrics", include_in_schema=True, tags=["ops"])
    def metrics():
        body = snapshot()
        return JSONResponse(
            status_code=200,
            content={
                **body,
                "count": body["requests_total"],
                "latency": body["latency_seconds_avg"],
            },
        )
