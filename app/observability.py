"""Request metrics: a count and a latency, served at /metrics.

The counters are process-wide and lock-protected; nothing here talks to a
network or a vendor.  A count without a latency (or the reverse) would let an
operator read a healthy number while the service stalls, so both are
reported.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {
    "started": time.time(),
    "requests": 0,
    "errors": 0,
    "by_path": {},
    "durations": [],
}
_MAX_DURATIONS = 2000


def record(path: str, status_code: int, seconds: float) -> None:
    with _LOCK:
        _STATE["requests"] += 1
        if int(status_code) >= 500:
            _STATE["errors"] += 1
        table = _STATE["by_path"]
        row = table.setdefault(str(path), {"count": 0, "errors": 0, "seconds": 0.0})
        row["count"] += 1
        row["seconds"] += float(seconds)
        if int(status_code) >= 500:
            row["errors"] += 1
        durations = _STATE["durations"]
        durations.append(float(seconds))
        if len(durations) > _MAX_DURATIONS:
            del durations[: len(durations) - _MAX_DURATIONS]


def snapshot() -> Dict[str, Any]:
    with _LOCK:
        durations = sorted(_STATE["durations"])
        count = _STATE["requests"]
        total = sum(durations)
        p95 = durations[int(0.95 * (len(durations) - 1))] if durations else 0.0
        return {
            "requests": count,
            "errors": _STATE["errors"],
            "duration_seconds_total": round(total, 6),
            "latency_p95_seconds": round(p95, 6),
            "by_path": {k: dict(v) for k, v in _STATE["by_path"].items()},
            "uptime_seconds": round(time.time() - _STATE["started"], 3),
        }


def render_prometheus() -> str:
    snap = snapshot()
    lines: List[str] = [
        "# HELP platform_requests_total Requests served by this process",
        "# TYPE platform_requests_total counter",
        "platform_requests_total %d" % snap["requests"],
        "# HELP platform_request_errors_total Requests answered 5xx",
        "# TYPE platform_request_errors_total counter",
        "platform_request_errors_total %d" % snap["errors"],
        "# HELP platform_request_duration_seconds_total Cumulative request duration",
        "# TYPE platform_request_duration_seconds_total counter",
        "platform_request_duration_seconds_total %.6f" % snap["duration_seconds_total"],
        "# HELP platform_request_latency_p95_seconds p95 request latency",
        "# TYPE platform_request_latency_p95_seconds gauge",
        "platform_request_latency_p95_seconds %.6f" % snap["latency_p95_seconds"],
        "# HELP platform_uptime_seconds Process uptime",
        "# TYPE platform_uptime_seconds gauge",
        "platform_uptime_seconds %.3f" % snap["uptime_seconds"],
    ]
    for path, row in sorted(snap["by_path"].items()):
        label = str(path).replace('"', "'")
        lines.append('platform_path_requests_total{path="%s"} %d' % (label, row["count"]))
        lines.append('platform_path_request_seconds_total{path="%s"} %.6f' % (label, row["seconds"]))
    return "\n".join(lines) + "\n"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            record(request.url.path, 500, time.perf_counter() - started)
            raise
        record(request.url.path, response.status_code, time.perf_counter() - started)
        return response


def mount_observability(app: FastAPI) -> None:
    app.add_middleware(MetricsMiddleware)
    app.add_api_route(
        "/metrics",
        lambda: PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4"),
        methods=["GET"],
        include_in_schema=False,
    )
