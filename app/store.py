"""Tenant-scoped SQLite/Postgres store over the alembic schema.

Schema belongs to alembic, never to connect(): this module issues no
CREATE TABLE. Every statement is a constant assembled once from the
declared columns (never from caller input) and every value travels as a
bound parameter. Rows are always filtered by the tenant resolved from
the authenticated principal.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app import db
from app.models import MODELS

STORAGE_PATH_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS") or "5000")
FASTAPI_SYNC_THREADPOOL = int(os.getenv("FASTAPI_SYNC_THREADPOOL") or "40")

#: entity -> declared, persisted columns (the alembic table has these plus id
#: and tenant_id). Frozen at import from the capability models.
COLUMNS: Dict[str, List[str]] = {cap: list(cls.FIELDS) for cap, cls in MODELS.items()}

_SQLITE_MAX_RETRIES = 8


def db_path() -> Path:
    return db.sqlite_path()


def connect():
    return db.connect()


def _coerce(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def _decode(row: Any) -> Dict[str, Any]:
    out = dict(row)
    for key in ("delay_days",):
        if isinstance(out.get(key), str) and out[key].isdigit():
            out[key] = int(out[key])
    for key in ("cap_reached",):
        if key in out and out[key] is not None:
            out[key] = bool(out[key])
    return out


def _columns(entity: str) -> List[str]:
    try:
        return COLUMNS[entity]
    except KeyError:
        raise KeyError(f"unknown store entity: {entity}") from None


def _insert_sql(entity: str) -> str:
    cols = _columns(entity)
    return "".join([
        "INSERT INTO ", entity, " (", ", ".join(cols + ["tenant_id"]), ") VALUES (",
        ", ".join(["?"] * (len(cols) + 1)), ")",
    ])


def _select_one_sql(entity: str) -> str:
    return "".join(["SELECT * FROM ", entity, " WHERE id = ? AND tenant_id = ?"])


def _select_all_sql(entity: str) -> str:
    return "".join(["SELECT * FROM ", entity, " WHERE tenant_id = ? ORDER BY id"])


def _update_sql(entity: str) -> str:
    cols = _columns(entity)
    return "".join([
        "UPDATE ", entity, " SET ", ", ".join([c + " = ?" for c in cols]),
        ", tenant_id = ? WHERE id = ? AND tenant_id = ?",
    ])


def _delete_sql(entity: str) -> str:
    return "".join(["DELETE FROM ", entity, " WHERE id = ? AND tenant_id = ?"])


def _run_read(statement: str, values: Iterable[Any]) -> List[Dict[str, Any]]:
    last: Optional[Exception] = None
    for attempt in range(_SQLITE_MAX_RETRIES):
        conn = connect()
        try:
            cursor = conn.execute(statement, tuple(values))
            return [_decode(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as exc:
            last = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.02 * (attempt + 1))
        finally:
            conn.close()
    assert last is not None
    raise last


def _record_for(entity: str, record: Dict[str, Any]) -> List[Any]:
    if not isinstance(record, dict):
        raise TypeError("a record must be a mapping")
    return [_coerce(record.get(column)) for column in _columns(entity)]


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    if not tenant_id:
        raise ValueError("tenant_id is required to save a record")
    values = _record_for(entity, record) + [tenant_id]
    conn = connect()
    try:
        cursor = conn.execute(_insert_sql(entity), tuple(values))
        conn.commit()
        record_id = cursor.lastrowid
    finally:
        conn.close()
    stored = get(entity, int(record_id), tenant_id=tenant_id)
    if stored is None:
        raise RuntimeError("the saved record could not be read back")
    return stored


def get(entity: str, record_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    rows = _run_read(_select_one_sql(entity), [int(record_id), tenant_id])
    return rows[0] if rows else None


def list_all(entity: str, tenant_id: str) -> List[Dict[str, Any]]:
    return _run_read(_select_all_sql(entity), [tenant_id])


def update(entity: str, record_id: int, record: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    values = _record_for(entity, record) + [tenant_id, int(record_id), tenant_id]
    conn = connect()
    try:
        conn.execute(_update_sql(entity), tuple(values))
        conn.commit()
    finally:
        conn.close()
    return get(entity, int(record_id), tenant_id=tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    conn = connect()
    try:
        cursor = conn.execute(_delete_sql(entity), (int(record_id), tenant_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def query(entity: str, tenant_id: str, contains: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    """Tenant-scoped case-insensitive search over the stored rows."""
    needle = str(contains or "").strip().lower()
    rows = list_all(entity, tenant_id)
    if needle:
        rows = [row for row in rows if needle in json.dumps(row, sort_keys=True, default=str).lower()]
    return rows[: max(1, int(limit))]


def enable_wal() -> None:
    db.enable_wal()
