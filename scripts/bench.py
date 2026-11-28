#!/usr/bin/env python3
"""Measure p95 latency for 200 concurrent health requests."""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app

N = 200


def _one(_i: int) -> float:
    started = time.perf_counter()
    with TestClient(app) as client:
        response = client.get("/health")
    if response.status_code not in (200, 503):
        raise RuntimeError("health answered %s" % response.status_code)
    return (time.perf_counter() - started) * 1000.0


def main() -> int:
    with ThreadPoolExecutor(max_workers=20) as pool:
        samples = list(pool.map(_one, range(N)))
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    print("requests=%d p50=%.1fms p95=%.1fms max=%.1fms" % (
        len(samples), statistics.median(samples), p95, samples[-1]))
    return 0 if p95 < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main())
