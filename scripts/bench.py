#!/usr/bin/env python3
"""A small p95 probe over the app in-process (no server, no factory port)."""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time

os.environ.setdefault("STORAGE_PATH", tempfile.mkdtemp(prefix="bench-"))
os.environ.setdefault("PLATFORM_TOKEN", "bench-token")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> int:
    headers = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
    latencies = []
    with TestClient(app) as client:
        for _ in range(200):
            started = time.perf_counter()
            response = client.get("/v1/compliance_dashboard", headers=headers)
            latencies.append((time.perf_counter() - started) * 1000)
            if response.status_code != 200:
                print("bench: HTTP %s" % response.status_code)
                return 1
    latencies.sort()
    p95 = latencies[int(round(0.95 * (len(latencies) - 1)))]
    print("requests=%d p50=%.2fms p95=%.2fms mean=%.2fms" % (
        len(latencies), statistics.median(latencies), p95, statistics.mean(latencies)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
