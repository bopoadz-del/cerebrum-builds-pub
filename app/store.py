"""Tenant-scoped persistence over the entity schema in alembic 0001.

``connect()`` routes through app.db and never issues CREATE TABLE: schema
belongs to alembic, not connect time. Every read and write is tenant-scoped.
The single persistence root is STORAGE_PATH (app.db resolves platform.db
beneath it).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa

from app import db, models

PERSISTENCE_ROOT_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = 15000
FASTAPI_SYNC_THREADPOOL = int(os.getenv("FASTAPI_SYNC_THREADPOOL") or 40)

_META = sa.MetaData()
_TABLES: Dict[tuple, sa.Table] = {}
_LOCK = threading.RLock()

COLUMNS: Dict[str, tuple] = {
    entity: tuple(["id", "tenant_id"] + list(cls.FIELDS) + ["created_at", "updated_at"])
    for entity, cls in models.MODELS.items()
}


def db_path():
    return db.sqlite_path()


def connect():
    return db.connect()


def enable_wal() -> None:
    if db.backend_name() != "sqlite":
        return
    conn = db.connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.commit()
    finally:
        conn.close()


def _table(entity: str) -> sa.Table:
    if entity not in models.MODELS:
        raise KeyError("unknown entity: %s" % entity)
    engine = db.get_engine()
    key = (str(engine.url), entity)
    with _LOCK:
        table = _TABLES.get(key)
        if table is None:
            table = sa.Table(entity, _META, autoload_with=engine)
            _TABLES[key] = table
        return table


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(record: Dict[str, Any]) -> str:
    clean: Dict[str, Any] = {}
    for key, value in (record or {}).items():
        if key in ("id", "tenant_id", "created_at", "updated_at"):
            continue
        if isinstance(value, (datetime, date)):
            clean[key] = value.isoformat()
        else:
            clean[key] = value
    return json.dumps(clean, sort_keys=True, default=str)


def _row_dict(row: Any) -> Dict[str, Any]:
    mapping = row._mapping
    try:
        payload = json.loads(mapping["data"] or "{}")
    except (TypeError, ValueError):
        payload = {}
    out: Dict[str, Any] = {"id": int(mapping["id"])}
    out.update(payload)
    out["tenant_id"] = mapping["tenant_id"]
    out["created_at"] = mapping["created_at"]
    out["updated_at"] = mapping["updated_at"]
    return out


def save(entity: str, record: Dict[str, Any], tenant_id: str = "") -> Dict[str, Any]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the store is tenant-scoped")
    table = _table(entity)
    stamp = _now()
    with db.get_engine().begin() as conn:
        result = conn.execute(
            sa.insert(table).values(
                tenant_id=str(tenant_id), data=_dump(record),
                created_at=stamp, updated_at=stamp,
            )
        )
        new_id = result.inserted_primary_key[0]
    saved = dict(record or {})
    saved.pop("id", None)
    saved["id"] = int(new_id)
    saved["tenant_id"] = str(tenant_id)
    saved["created_at"] = stamp
    saved["updated_at"] = stamp
    return saved


def get(entity: str, record_id: int, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the store is tenant-scoped")
    table = _table(entity)
    with db.get_engine().connect() as conn:
        row = conn.execute(
            sa.select(table).where(
                table.c.id == int(record_id), table.c.tenant_id == str(tenant_id)
            )
        ).first()
    return _row_dict(row) if row is not None else None


def list_all(entity: str, tenant_id: str = "") -> List[Dict[str, Any]]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the store is tenant-scoped")
    table = _table(entity)
    with db.get_engine().connect() as conn:
        rows = conn.execute(
            sa.select(table)
            .where(table.c.tenant_id == str(tenant_id))
            .order_by(table.c.id)
        ).fetchall()
    return [_row_dict(row) for row in rows]


def tenant_of(entity: str, record_id: int) -> str:
    """The tenant a stored record belongs to (used to scope its queue key)."""
    table = _table(entity)
    with db.get_engine().connect() as conn:
        row = conn.execute(
            sa.select(table.c.tenant_id).where(table.c.id == int(record_id))
        ).first()
    return str(row[0]) if row is not None else ""


def query(entity: str, tenant_id: str = "", **filters: Any) -> List[Dict[str, Any]]:
    rows = list_all(entity, tenant_id=tenant_id)
    if not filters:
        return rows
    return [
        row for row in rows
        if all(row.get(key) == value for key, value in filters.items())
    ]


def update(entity: str, record_id: int, record: Dict[str, Any], tenant_id: str = "") -> Optional[Dict[str, Any]]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the store is tenant-scoped")
    current = get(entity, record_id, tenant_id=tenant_id)
    if current is None:
        return None
    merged = dict(current)
    merged.update(record or {})
    for key in ("id", "tenant_id", "created_at", "updated_at"):
        merged.pop(key, None)
    table = _table(entity)
    with db.get_engine().begin() as conn:
        conn.execute(
            sa.update(table)
            .where(table.c.id == int(record_id), table.c.tenant_id == str(tenant_id))
            .values(data=_dump(merged), updated_at=_now())
        )
    return get(entity, record_id, tenant_id=tenant_id)


def delete(entity: str, record_id: int, tenant_id: str = "") -> bool:
    if not tenant_id:
        raise ValueError("tenant_id is required: the store is tenant-scoped")
    table = _table(entity)
    with db.get_engine().begin() as conn:
        result = conn.execute(
            sa.delete(table).where(
                table.c.id == int(record_id), table.c.tenant_id == str(tenant_id)
            )
        )
    return bool(result.rowcount)
