"""Request metrics without a metrics server.

Counts and cumulative latency are kept in process; ``/metrics`` renders them
in the text format a scraper expects. No network, no background exporter.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

_LOCK = threading.Lock()
_COUNTS: Dict[Tuple[str, int], int] = {}
_LATENCY_SUM = 0.0
_LATENCY_COUNT = 0
_START = time.time()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        global _LATENCY_SUM, _LATENCY_COUNT
        with _LOCK:
            key = (request.method, int(response.status_code))
            _COUNTS[key] = _COUNTS.get(key, 0) + 1
            _LATENCY_SUM += elapsed
            _LATENCY_COUNT += 1
        return response


def render_metrics() -> str:
    with _LOCK:
        lines = [
            "# HELP platform_requests_total Requests served, by method and status.",
            "# TYPE platform_requests_total counter",
        ]
        for (method, status), count in sorted(_COUNTS.items()):
            lines.append(
                'platform_requests_total{method="%s",status="%d"} %d' % (method, status, count)
            )
        average = (_LATENCY_SUM / _LATENCY_COUNT) if _LATENCY_COUNT else 0.0
        lines.extend(
            [
                "# HELP platform_request_latency_seconds_mean Mean request latency.",
                "# TYPE platform_request_latency_seconds_mean gauge",
                "platform_request_latency_seconds_mean %.6f" % average,
                "# HELP platform_uptime_seconds Process uptime.",
                "# TYPE platform_uptime_seconds gauge",
                "platform_uptime_seconds %.3f" % (time.time() - _START),
            ]
        )
    return "\n".join(lines) + "\n"


def metrics_response() -> PlainTextResponse:
    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4")


def install_metrics(app) -> None:
    app.add_middleware(MetricsMiddleware)
    app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=False)
