#!/usr/bin/env python3
"""Measure p95 latency for 200 concurrent requests against the booted service.

Starts the product's own server on a free loopback port (the exact PID it
started is the one it stops), drives 200 requests at concurrency 40 -- half of
them creates, half reads -- and prints the number the floor reads:

    STORE_BENCH_P95_MS=<value>

The workload goes through the real HTTP stack, so the figure covers routing,
validation, the handler, the tenant-scoped write and the response, not an
in-process shortcut.
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUESTS = 200
CONCURRENCY = 40
TOKEN = os.environ.get("PLATFORM_TOKEN") or "bench-token"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(env):
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning", "--no-access-log"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:%d" % port
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("the service exited before answering")
        try:
            urllib.request.urlopen(base + "/health", timeout=2).close()
            return base, proc
        except urllib.error.HTTPError:
            return base, proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("the service did not answer")


def main() -> int:
    sys.path.insert(0, ROOT)
    from app import kernel_bridge
    from app.models import MODELS
    from app.validation import sample_for_model

    capability = kernel_bridge.default_capability()
    body = json.dumps(sample_for_model(MODELS[capability])).encode()
    headers = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}

    env = dict(os.environ, PLATFORM_TOKEN=TOKEN)
    env.setdefault("STORAGE_PATH", tempfile.mkdtemp(prefix="platform-bench-"))
    base, proc = _serve(env)
    try:
        def timed(request: urllib.request.Request) -> float:
            started = time.perf_counter()
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()
            return (time.perf_counter() - started) * 1000.0

        timed(urllib.request.Request(base + "/v1/" + capability, data=body, headers=headers, method="POST"))

        def one(index: int) -> float:
            method = "POST" if index % 2 else "GET"
            return timed(
                urllib.request.Request(
                    base + "/v1/" + capability,
                    data=body if method == "POST" else None,
                    headers=headers,
                    method=method,
                )
            )

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            timings = sorted(pool.map(one, range(REQUESTS)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    p95 = timings[max(0, int(round(0.95 * (len(timings) - 1))))]
    print("capability: %s, requests: %d, concurrency: %d" % (capability, REQUESTS, CONCURRENCY))
    print("median: %.1f ms, p95: %.1f ms, max: %.1f ms" % (
        statistics.median(timings), p95, timings[-1]))
    print("STORE_BENCH_P95_MS=%.1f" % p95)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
