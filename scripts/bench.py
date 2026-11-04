#!/usr/bin/env python3
"""A small latency bench: create, list and read through the real routes.

CI runs this so a change that makes the product correct but slow is visible
before a customer sees it. It prints the p95 of each operation and exits
non-zero when the p95 of any operation is over the 500 ms budget.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BUDGET_MS = 500.0
SAMPLES = 40


def main() -> int:
    os.environ.setdefault("STORAGE_PATH", tempfile.mkdtemp(prefix="bench-"))
    os.environ.setdefault("PLATFORM_TOKEN", os.urandom(16).hex())

    from fastapi.testclient import TestClient

    from app.main import app

    headers = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
    capability = "document_register"
    timings = {"create": [], "list": [], "read": []}

    with TestClient(app) as client:
        for index in range(SAMPLES):
            started = time.perf_counter()
            response = client.post(
                "/v1/" + capability,
                json={"reference": "BENCH-%03d" % index, "document_type": "drawing"},
                headers=headers,
            )
            timings["create"].append((time.perf_counter() - started) * 1000.0)
            response.raise_for_status()

            started = time.perf_counter()
            listing = client.get("/v1/" + capability, headers=headers)
            timings["list"].append((time.perf_counter() - started) * 1000.0)
            listing.raise_for_status()

            rows = listing.json().get("items") or []
            record_id = rows[-1]["id"] if rows else 1
            started = time.perf_counter()
            one = client.get("/v1/%s/%s" % (capability, record_id), headers=headers)
            timings["read"].append((time.perf_counter() - started) * 1000.0)
            one.raise_for_status()

    failed = False
    for name, samples in timings.items():
        ordered = sorted(samples)
        p95 = ordered[int(0.95 * (len(ordered) - 1))]
        flag = "FAIL" if p95 >= BUDGET_MS else "ok"
        if p95 >= BUDGET_MS:
            failed = True
        print("%-8s n=%d mean=%.2fms p95=%.2fms %s"
              % (name, len(samples), statistics.fmean(samples), p95, flag))
    print("budget: p95 < %.0fms" % BUDGET_MS)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
