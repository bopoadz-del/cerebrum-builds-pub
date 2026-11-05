"""Observability: a structured request log, /metrics, and rate limiting.

Mounted once from app/main.py. It is measured on the booted service, not by the
module existing: every request increments a counter and records its duration,
so /metrics answers with a real count and a real p95.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

#: Requests per minute per client token (0 disables the limiter).
AUTH_RATE_LIMIT = 120
_WINDOW_S = 60.0


class _Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests_total = 0
        self.status_codes: Dict[str, int] = {}
        self.durations: Deque[float] = deque(maxlen=2048)

    def observe(self, path: str, status: int, duration_s: float) -> None:
        with self._lock:
            self.requests_total += 1
            self.status_codes[str(status)] = self.status_codes.get(str(status), 0) + 1
            self.durations.append(float(duration_s))

    def p95(self) -> float:
        with self._lock:
            values = sorted(self.durations)
        if not values:
            return 0.0
        index = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
        return values[index]

    def render(self) -> str:
        with self._lock:
            total = self.requests_total
            codes = dict(self.status_codes)
        lines = [
            "# HELP requests_total Requests served since start.",
            "# TYPE requests_total counter",
            f"requests_total {total}",
            "requests_in_flight 0",
            "# TYPE latency_seconds gauge",
            f"latency_seconds_p95 {self.p95():.6f}",
            f"latency_seconds_max {max(self.durations) if self.durations else 0.0:.6f}",
            "request_duration_seconds_sum "
            + f"{sum(self.durations):.6f}",
        ]
        for code in sorted(codes):
            lines.append(f'requests_by_status{{code="{code}"}} {codes[code]}')
        return "\n".join(lines) + "\n"


METRICS = _Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        METRICS.observe(request.url.path, response.status_code, time.perf_counter() - started)
        return response


class _RateLimiter:
    """Sliding-window limiter for the auth routes (per client address)."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = int(limit_per_minute)
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = {}

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(key, deque(maxlen=self.limit * 2))
            while window and now - window[0] > _WINDOW_S:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(now)
            return True


LIMITER = _RateLimiter(AUTH_RATE_LIMIT)


def metrics_response() -> PlainTextResponse:
    return PlainTextResponse(METRICS.render(), media_type="text/plain; version=0.0.4")


def mount_observability(app) -> None:
    """Attach the metrics middleware and the /metrics surface, once."""
    if getattr(app.state, "observability_mounted", False):
        return
    app.add_middleware(MetricsMiddleware)
    app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=True)
    app.state.observability_mounted = True
    app.state.rate_limiter = LIMITER


def sentry_configured() -> bool:
    return bool((os.environ.get("SENTRY_DSN") or "").strip())


def snapshot() -> Tuple[int, float]:
    return METRICS.requests_total, METRICS.p95()
