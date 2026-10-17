"""Hotel Booking Platform FastAPI entry. Bind 0.0.0.0:$PORT on Render."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.auth import install_cors
from app.rag_routes import router as rag_router
from app.routes import router as capability_router
from app.store import db_path, ensure_schema, reset_connection, storage_root

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _run_migrations() -> None:
    reset_connection()
    ensure_schema()
    try:
        from alembic import command
        from alembic.config import Config

        ini = Path(__file__).resolve().parents[1] / "alembic.ini"
        if ini.is_file():
            cfg = Config(str(ini))
            cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path()}")
            command.upgrade(cfg, "head")
    except Exception:
        ensure_schema()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage_root()
    _run_migrations()
    yield


app = FastAPI(
    title="Hotel Booking Platform",
    version="1.0.0",
    description=(
        "Cerebrum Hotel Booking Platform — guests search, compare, and reserve rooms; "
        "operators manage inventory, pricing, reviews, and notifications. "
        "Mutations require a bearer operator token."
    ),
    lifespan=lifespan,
)
install_cors(app)
app.include_router(capability_router)
app.include_router(rag_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict:
    root = storage_root()
    if not os.access(root, os.W_OK):
        raise HTTPException(status_code=503, detail="storage not writable")
    try:
        ensure_schema()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"schema unavailable: {exc}") from exc
    return {"ok": True, "status": "ok", "storage": str(root), "db": str(db_path())}


@app.get("/", response_class=HTMLResponse)
def ui_index() -> HTMLResponse:
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    raise HTTPException(status_code=503, detail="ui missing")


@app.get("/ui", response_class=HTMLResponse)
def ui_alias() -> HTMLResponse:
    return ui_index()


@app.get("/openapi.json", include_in_schema=False)
def committed_openapi_fallback():
    # BA jail: committed spec lives only at docs/openapi.json.
    docs_copy = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    if docs_copy.is_file():
        return FileResponse(docs_copy)
    return app.openapi()
