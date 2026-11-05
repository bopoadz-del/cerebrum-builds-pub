#!/usr/bin/env python3
"""Measure request latency for the platform.

Runs the real FastAPI app in-process through TestClient (no port, no
network) and prints p50/p95/p99 for a health read and a tenant-scoped list.
The Store gate's advisory bench reads the printed p95.
"""

from __future__ import annotations

import math
import os
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("STORAGE_PATH", tempfile.mkdtemp(prefix="fleet-bench-"))
os.environ.setdefault("PLATFORM_TOKEN", "bench-token")


def _p95(samples):
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[index]


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app

    auth = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
    with TestClient(app) as client:
        client.get("/health")
        paths = [("/health", None), ("/v1/capabilities", auth)]

        def timed(path, headers):
            started = time.perf_counter()
            response = client.get(path, headers=headers or {})
            elapsed = (time.perf_counter() - started) * 1000.0
            if response.status_code != 200:
                raise RuntimeError("%s answered HTTP %s" % (path, response.status_code))
            return elapsed

        with ThreadPoolExecutor(max_workers=40) as pool:
            for path, headers in paths:
                samples = list(pool.map(lambda _: timed(path, headers), range(200)))
                print(
                    "%s n=200 p50=%.1fms p95=%.1fms p99=%.1fms"
                    % (
                        path,
                        statistics.median(samples),
                        _p95(samples),
                        sorted(samples)[-1],
                    )
                )
                if _p95(samples) > 500.0:
                    print("p95 above the 500ms reference bar", file=sys.stderr)
                    return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
