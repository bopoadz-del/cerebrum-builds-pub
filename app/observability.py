"""Metrics, error reporting and rate limiting.

Written by the factory. Mount it once in app/main.py:

    from app.observability import mount_observability
    mount_observability(app)

GET /metrics then answers request counts and latency (the floor's
metrics_served), SENTRY_DSN is honoured when set, and auth routes are rate
limited.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

#: Requests seen and seconds spent, per method+path. In-process on purpose:
#: a pilot runs one container, and a metrics backend is the operator's call.
_COUNTS: Dict[Tuple[str, str], int] = defaultdict(int)
_SECONDS: Dict[Tuple[str, str], float] = defaultdict(float)
_STATUS: Dict[int, int] = defaultdict(int)

#: Auth attempts per client, for the rate limit.
_ATTEMPTS: Dict[str, Deque[float]] = defaultdict(deque)
#: FAILED authentications per client, for the throttle this product actually
#: needs: every /v1 route authenticates with a bearer token, and none of them
#: matches AUTH_PREFIXES, so the attempts above would guard nothing here.
_FAILED_AUTH: Dict[str, Deque[float]] = defaultdict(deque)

RATE_LIMIT_WINDOW_S = float(os.environ.get("AUTH_RATE_WINDOW_S", "60"))
RATE_LIMIT_MAX = int(os.environ.get("AUTH_RATE_MAX", "20"))
#: Failed authentications one client may spend per window before the
#: platform answers 429 instead of 401. Distinct from RATE_LIMIT_MAX: a
#: legitimate client with a mistyped token must not lock itself out on the
#: same allowance a token guesser gets.
AUTH_FAILURE_MAX = int(os.environ.get("AUTH_FAILURE_MAX", "60"))
AUTH_PREFIXES = ("/v1/auth", "/v1/login", "/v1/token", "/auth", "/login")


def _is_auth_route(path):
    """True for the authentication endpoints, matched on a segment boundary.

    A bare ``startswith("/v1/auth")`` also matched the ``auth_roles_admin``
    capability, so a single client could 429 a normal operator capability
    while the read surface had no limiter at all.
    """
    low = path.lower().rstrip("/") or "/"
    return any(low == prefix or low.startswith(prefix + "/") for prefix in AUTH_PREFIXES)


def _rate_limited(client):
    """True when this client has spent its auth attempts for the window."""
    now = time.monotonic()
    seen = _ATTEMPTS[client]
    while seen and now - seen[0] > RATE_LIMIT_WINDOW_S:
        seen.popleft()
    if len(seen) >= RATE_LIMIT_MAX:
        return True
    seen.append(now)
    return False


def failed_auth_limited(client: str) -> bool:
    """Record one failed authentication; True once the client has spent its
    allowance for the window. Called from app.auth on every refused token."""
    now = time.monotonic()
    seen = _FAILED_AUTH[str(client or "unknown")]
    while seen and now - seen[0] > RATE_LIMIT_WINDOW_S:
        seen.popleft()
    if len(seen) >= AUTH_FAILURE_MAX:
        return True
    seen.append(now)
    return False


def _init_sentry():
    """Honour SENTRY_DSN when both the variable and the SDK are present."""
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return "unset"
    try:
        import sentry_sdk
    except ImportError:
        return "dsn set but sentry-sdk is not installed"
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)
    return "enabled"


def mount_observability(app: Any) -> None:
    """Add the middleware and the /metrics route. Call once, at startup."""
    sentry_state = _init_sentry()

    @app.middleware("http")
    async def _observe(request: Request, call_next):
        path = request.url.path
        if _is_auth_route(path):
            client = request.client.host if request.client else "unknown"
            if _rate_limited(client):
                return JSONResponse(
                    {"ok": False, "error": "too many attempts"}, status_code=429
                )
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        key = (request.method, path)
        _COUNTS[key] += 1
        _SECONDS[key] += elapsed
        _STATUS[response.status_code] += 1
        return response

    @app.get("/metrics")
    def metrics():
        lines = [
            "# HELP http_requests_total Requests handled since boot.",
            "# TYPE http_requests_total counter",
        ]
        for (method, path), count in sorted(_COUNTS.items()):
            lines.append(
                "http_requests_total{method=%r,path=%r} %d" % (method, path, count)
            )
        lines.append(
            "# HELP http_request_duration_seconds_total Seconds spent handling."
        )
        lines.append("# TYPE http_request_duration_seconds_total counter")
        for (method, path), seconds in sorted(_SECONDS.items()):
            lines.append(
                "http_request_duration_seconds_total{method=%r,path=%r} %.6f"
                % (method, path, seconds)
            )
        for status, count in sorted(_STATUS.items()):
            lines.append("http_responses_total{status=%d} %d" % (status, count))
        lines.append("# sentry: " + sentry_state)
        return PlainTextResponse(chr(10).join(lines) + chr(10))
