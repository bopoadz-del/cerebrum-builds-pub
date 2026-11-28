"""Fail-closed process health for Render and the local drill.

A 200 means this process is serving, STORAGE_PATH is a writable
persistent disk, the configured database answers, and Alembic is at
head. Anything else is 503. Unconditional ok:true is F1 and is
forbidden here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi.responses import JSONResponse

from app.revision import current_app_mark, current_app_revision


def _storage_root() -> Path | None:
    raw = os.getenv("STORAGE_PATH")
    if not raw:
        return None
    return Path(raw)


def evaluate_health() -> Tuple[int, Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []

    checks.append(
        {
            "name": "process",
            "ok": True,
            "detail": f"pid={os.getpid()}",
        }
    )

    storage = _storage_root()
    if storage is None:
        disk_ok, disk_detail = False, "STORAGE_PATH unset"
    elif not storage.exists():
        disk_ok, disk_detail = False, f"missing {storage}"
    elif not storage.is_dir():
        # A writable FILE passes exists() and os.access(); the service
        # cannot keep a database or uploads under it.
        disk_ok, disk_detail = False, f"not a directory {storage}"
    elif not os.access(storage, os.R_OK | os.W_OK):
        disk_ok, disk_detail = False, f"not writable {storage}"
    else:
        disk_ok, disk_detail = True, str(storage)
    checks.append(
        {"name": "persistent_disk", "ok": disk_ok, "detail": disk_detail}
    )

    # The database the platform actually runs on -- app.db decides
    # (Postgres when DATABASE_URL says so, else the SQLite file). A
    # SQLite-file check here read 'platform.db missing' on every healthy
    # Postgres deployment and held /health at 503.
    db_ok = False
    db_detail = "not checked"
    if not disk_ok:
        db_detail = "persistent disk missing"
    else:
        try:
            from app import db as _db

            backend = _db.backend_name()
            if backend == "sqlite" and not _db.sqlite_path().exists():
                db_detail = f"{_db.sqlite_path().name} missing"
            else:
                conn = _db.connect()
                try:
                    if backend == "postgres":
                        from sqlalchemy import text as _sql_text

                        conn.execute(_sql_text("SELECT 1"))
                    else:
                        conn.execute("SELECT 1")
                finally:
                    conn.close()
                db_ok = True
                db_detail = backend
        except Exception as exc:  # noqa: BLE001 -- health must not raise
            db_detail = type(exc).__name__
    checks.append({"name": "database", "ok": db_ok, "detail": db_detail})

    mig_ok = False
    mig_detail = "not checked"
    if not db_ok:
        mig_detail = "database missing"
    else:
        try:
            from app.migrations import current_revision, head_revision

            current = current_revision()
            head = head_revision()
            mig_ok = bool(current) and current == head
            mig_detail = f"current={current} head={head}"
        except Exception as exc:  # noqa: BLE001 — health must not raise
            mig_detail = type(exc).__name__
    checks.append({"name": "migrations", "ok": mig_ok, "detail": mig_detail})

    ok = all(bool(item["ok"]) for item in checks)
    body = {
        "ok": ok,
        "status": "ok" if ok else "not_ready",
        "checks": checks,
        "revision": current_app_revision(),
        "mark": current_app_mark(),
    }
    return (200 if ok else 503, body)


def health_response() -> JSONResponse:
    code, body = evaluate_health()
    return JSONResponse(status_code=code, content=body)
