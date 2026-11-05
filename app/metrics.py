"""Request count and latency, served at /metrics.

The console and the Store gate both read this: a request total and the
latency the process actually measured.
"""

from __future__ import annotations

import threading
import time
from typing import Dict

_LOCK = threading.Lock()
_STATE: Dict[str, float] = {
    "requests_total": 0.0,
    "latency_ms_total": 0.0,
    "latency_ms_max": 0.0,
}


def observe(duration_ms: float) -> None:
    with _LOCK:
        _STATE["requests_total"] += 1
        _STATE["latency_ms_total"] += float(duration_ms)
        if duration_ms > _STATE["latency_ms_max"]:
            _STATE["latency_ms_max"] = float(duration_ms)


def snapshot() -> Dict[str, float]:
    with _LOCK:
        total = _STATE["requests_total"]
        return {
            "requests_total": total,
            "latency_ms_total": round(_STATE["latency_ms_total"], 3),
            "latency_ms_avg": round(_STATE["latency_ms_total"] / total, 3) if total else 0.0,
            "latency_ms_max": round(_STATE["latency_ms_max"], 3),
        }


class MetricsMiddleware:
    """ASGI-level timing so every request is counted, including refusals."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            observe((time.perf_counter() - started) * 1000.0)


def render() -> str:
    stats = snapshot()
    lines = [
        "# HELP platform_requests_total Requests served by this process.",
        "# TYPE platform_requests_total counter",
        f"platform_requests_total {int(stats['requests_total'])}",
        "# HELP platform_request_latency_ms Request latency in milliseconds.",
        "# TYPE platform_request_latency_ms gauge",
        f'platform_request_latency_ms{{stat="avg"}} {stats["latency_ms_avg"]}',
        f'platform_request_latency_ms{{stat="max"}} {stats["latency_ms_max"]}',
        f'platform_request_latency_ms{{stat="total"}} {stats["latency_ms_total"]}',
        "",
    ]
    return "\n".join(lines)
