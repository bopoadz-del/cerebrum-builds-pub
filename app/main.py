"""Entrypoint for the the project platform.

Runs standalone: ``uvicorn app.main:app``. Network posture P1 (offline
strict): no outbound dependency at runtime. GET /health is fail-closed;
GET / serves the operator console at app/static/index.html.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.health import health_response
from app.observe import install_observability
from app.rag_routes import router as rag_router
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.migrations import upgrade_head
    from app.observe import configure_logging

    upgrade_head()
    try:
        from app import store

        store.enable_wal()
    except Exception:  # noqa: BLE001 - WAL is a SQLite-only optimisation
        import logging

        logging.getLogger(__name__).exception("WAL enable skipped")
    configure_logging()
    yield


def _int_setting(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError("%s must be an integer, got %r" % (name, raw)) from exc


MAX_REQUEST_BYTES = _int_setting("REQUEST_MAX_BYTES", 1_048_576)

app = FastAPI(
    title="the project Platform",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _too_large() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "ok": False,
            "error_kind": "payload_too_large",
            "error": "request body exceeds %d bytes" % MAX_REQUEST_BYTES,
        },
    )


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit():
        if int(declared) > MAX_REQUEST_BYTES:
            return _too_large()
        return await call_next(request)
    chunks: list = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            return _too_large()
        chunks.append(chunk)
    request._body = b"".join(chunks)
    return await call_next(request)


install_observability(app)
try:
    from app.observability import mount_observability

    mount_observability(app)
except Exception:  # noqa: BLE001 - observability must not refuse boot
    import logging

    logging.getLogger(__name__).exception("observability not mounted")
app.include_router(router, prefix="/v1")
app.include_router(rag_router, prefix="/v1")


@app.get("/health")
def health():
    return health_response()


@app.get("/")
def ui_root():
    here = Path(__file__).resolve().parent
    for candidate in (here / "static" / "index.html", here.parent / "frontend" / "index.html"):
        if candidate.is_file():
            return FileResponse(candidate, media_type="text/html")
    return HTMLResponse(
        "<!doctype html><html><body><h1>the project</h1>"
        "<p>The operator console is not built into this image.</p></body></html>"
    )
