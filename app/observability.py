"""Request metrics and structured logging mount for the platform."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.observe import install_observability

_COUNTS: Dict[str, int] = defaultdict(int)
_LATENCY_MS: Dict[str, float] = defaultdict(float)
_STARTED = time.time()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        if path != "/metrics":
            _COUNTS["requests"] += 1
            _COUNTS["responses_" + str(response.status_code)] += 1
            elapsed = (time.perf_counter() - started) * 1000.0
            _LATENCY_MS["total"] += elapsed
            _LATENCY_MS["max"] = max(_LATENCY_MS["max"], elapsed)
        return response


def snapshot() -> Dict[str, float]:
    requests = _COUNTS.get("requests", 0)
    return {
        "requests": requests,
        "latency_ms_total": round(_LATENCY_MS.get("total", 0.0), 3),
        "latency_ms_avg": round(_LATENCY_MS["total"] / requests, 3) if requests else 0.0,
        "latency_ms_max": round(_LATENCY_MS.get("max", 0.0), 3),
        "uptime_s": round(time.time() - _STARTED, 3),
    }


def mount_observability(app) -> None:
    install_observability(app)
    app.add_middleware(MetricsMiddleware)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)


async def metrics_endpoint() -> JSONResponse:
    return JSONResponse(snapshot())
