#!/usr/bin/env python3
"""A tiny p95 bench over the booted app: /health and one capability POST.

CI runs this so a latency regression is visible before the Store gate. It
prints one JSON line; the Store gate measures the same number from the booted
image.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("STORAGE_PATH", tempfile.mkdtemp(prefix="bench-"))
os.environ.setdefault("PLATFORM_TOKEN", "bench-local-token")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> int:
    token = os.environ["PLATFORM_TOKEN"]
    headers = {"Authorization": "Bearer " + token}
    timings = []
    with TestClient(app) as client:
        client.get("/health")
        for _ in range(20):
            started = time.perf_counter()
            client.get("/health")
            timings.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        client.post("/v1/contract_source_of_record", json={"reference": "bench"}, headers=headers)
        timings.append((time.perf_counter() - started) * 1000)
    timings.sort()
    p95 = timings[min(len(timings) - 1, int(round(0.95 * (len(timings) - 1))))]
    print(json.dumps({"p95_ms": round(p95, 2), "median_ms": round(statistics.median(timings), 2)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
