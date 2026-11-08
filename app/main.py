"""The ASGI application.

Boot order is the contract: schema first (Alembic), then the locked block
check, then traffic. Health is the shipped ``app/health.py`` -- fail-closed on
process, disk, database and migration head -- and observability is mounted
once, so /metrics reports this process rather than the module existing.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__ as platform_version
from app import dispatch, health, observe, observability, sources
from app.routes import INGEST, KERNEL, ROUTER

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

#: The largest request body the edge accepts, checked from Content-Length
#: BEFORE the framework parses it: an unauthenticated caller cannot make the
#: process spool an arbitrarily large upload to disk and then be refused.
#: Uploads are bounded at 25 MB in the intake route; this leaves multipart
#: framing room above that.
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES") or 32 * 1024 * 1024)

TITLE = "Harbourline Civil Works Contracts Administration"
DESCRIPTION = (
    "Contracts administration for a single civil-works project: interim "
    "payment certificates measured against BOQ lines, time and delay-damages "
    "tracking, inspection and test-plan records, a revision-controlled "
    "document register, a clause register, and the commercial position "
    "aggregated from the tenant's own records. The uploaded excerpt and bill "
    "of quantities are the source every figure cites."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import migrations

    migrations.upgrade_head()
    # Alembic's env.py runs fileConfig(), which resets the root logger. Install
    # the structured request log again after migrations so request lines and
    # the request.jsonl file survive boot -- not just import.
    observe.configure_logging()
    dispatch.verify_locked_blocks()
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False


app = FastAPI(
    title=TITLE,
    description=DESCRIPTION,
    version=platform_version,
    lifespan=lifespan,
)

@app.middleware("http")
async def refuse_oversized_bodies(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            too_large = int(declared) > MAX_REQUEST_BYTES
        except ValueError:
            too_large = True
        if too_large:
            return JSONResponse(
                status_code=413,
                content={
                    "ok": False,
                    "error": "request body exceeds the declared bound",
                    "error_kind": "payload_too_large",
                    "max_bytes": MAX_REQUEST_BYTES,
                },
            )
    return await call_next(request)


observe.install_observability(app)
observability.mount_observability(app)

app.include_router(KERNEL)
app.include_router(INGEST)
app.include_router(ROUTER)


@app.get("/health", tags=["ops"])
def health_route():
    """The shipped fail-closed health body (process, disk, database, head)."""
    return health.health_response()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def console(request: Request):
    """The operator console: app/static/index.html, the platform's one UI.

    The page carries no credential of its own: the operator pastes the deploy
    token into the console, which keeps it in sessionStorage and sends it as
    the bearer header on the console's own calls. A request without a token
    still answers 401, so serving the page opens nothing.
    """
    if INDEX_FILE.is_file():
        page = INDEX_FILE.read_text(encoding="utf-8")
        page = page.replace("{{PRODUCT_ID}}", sources.PRODUCT_ID).replace(
            "{{PRODUCT_NAME}}", sources.PROJECT_NAME
        )
        response = HTMLResponse(page)
    else:
        response = HTMLResponse(
            "<!doctype html><html><body><h1>Harbourline Civil Works Contracts Administration</h1>"
            "<p>The console asset is missing from this image.</p></body></html>",
            status_code=200,
        )
    return response


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
