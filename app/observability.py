"""Request metrics and optional error reporting, mounted once by app.main."""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Deque, Dict

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

_COUNTS: Dict[str, int] = {}
_MAX_LABELS = 64
_LATENCIES: Deque[float] = deque(maxlen=2048)
_TOTAL = {"requests": 0}


def _route_label(request: Request) -> str:
    """The matched route template, never the raw path: a unique path per
    request would grow the label map without bound."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return "unmatched"


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _render() -> str:
    total = _TOTAL["requests"]
    average = (sum(_LATENCIES) / len(_LATENCIES)) if _LATENCIES else 0.0
    lines = [
        "# HELP platform_requests_total Total HTTP requests served",
        "# TYPE platform_requests_total counter",
        "platform_requests_total %d" % total,
        "# HELP platform_request_latency_seconds Request latency summary",
        "# TYPE platform_request_latency_seconds summary",
        "platform_request_latency_seconds_avg %.6f" % average,
        "platform_request_latency_seconds_p95 %.6f" % _percentile(_LATENCIES, 0.95),
        "platform_request_latency_seconds_p99 %.6f" % _percentile(_LATENCIES, 0.99),
    ]
    for path, count in sorted(_COUNTS.items()):
        lines.append('platform_requests_by_path{route="%s"} %d' % (_escape(path), count))
    return "\n".join(lines) + "\n"


def mount_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def _timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        _TOTAL["requests"] += 1
        _LATENCIES.append(elapsed)
        label = _route_label(request)
        if label in _COUNTS or len(_COUNTS) < _MAX_LABELS:
            _COUNTS[label] = _COUNTS.get(label, 0) + 1
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(_render())

    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if dsn:
        try:  # pragma: no cover -- optional reporting dependency
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE") or 0.0))
        except Exception:  # noqa: BLE001 -- reporting never blocks serving
            pass
