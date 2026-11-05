#!/usr/bin/env python3
"""Reference-box benchmark: 200 concurrent health requests, p95 printed."""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


def main() -> int:
    with TestClient(app) as client:
        client.get("/health")

        def one(_):
            started = time.perf_counter()
            response = client.get("/health")
            return response.status_code, time.perf_counter() - started

        with ThreadPoolExecutor(max_workers=40) as pool:
            results = list(pool.map(one, range(200)))
    latencies = sorted(ms for _status, ms in results)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print("requests=200 failures=%d p95_ms=%.2f" % (sum(1 for s, _ in results if s != 200), p95 * 1000))
    return 0 if p95 < 0.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
