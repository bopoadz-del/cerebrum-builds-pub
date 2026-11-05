"""Tenant-scoped persistence over the database app.db chose.

Every table is the capability's own entity (its handler module stem). Rows
carry ``tenant_id`` and a JSON ``data`` payload so a capability can evolve
its fields without a migration per field; the columns the platform itself
queries (reference, status) are lifted out for indexing and audit.

Statements are SQLAlchemy Core statements built from the declared table and
column objects, with values bound. No f-string SQL, no CREATE TABLE here.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    delete as sa_delete,
    select,
    update as sa_update,
)

from app import db as app_db

STORAGE_ROOT_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = app_db.SQLITE_BUSY_TIMEOUT_MS
FASTAPI_SYNC_THREADPOOL = int(os.getenv("FASTAPI_SYNC_THREADPOOL", "40"))

#: SQLite serialises writers inside the file anyway; taking a process lock
#: first turns lock contention into a short queue instead of a busy-timeout
#: storm on network/overlay filesystems. PostgreSQL writes are independent.
_WRITE_LOCK = threading.RLock()
_METADATA = MetaData()
_TABLES: Dict[str, Table] = {}

#: Entities written by the platform beyond the capability tables.
SYSTEM_ENTITIES = ("work_queue", "idempotency")


def _table(entity: str) -> Table:
    name = str(entity)
    existing = _TABLES.get(name)
    if existing is not None:
        return existing
    table = Table(
        name,
        _METADATA,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("tenant_id", String(128), nullable=False),
        Column("reference", String(255), nullable=True),
        Column("status", String(64), nullable=True),
        Column("data", Text, nullable=False, default="{}"),
        Column("created_at", String(64), nullable=True),
        Column("updated_at", String(64), nullable=True),
        extend_existing=True,
    )
    _TABLES[name] = table
    return table


def db_path():
    """The SQLite file when SQLite is live; ``None`` on PostgreSQL."""
    if app_db.backend_name() != "sqlite":
        return None
    return app_db.sqlite_path()


def connect():
    """Connect through app.db -- never a second database of our own."""
    return app_db.connect()


def _write_guard():
    return _WRITE_LOCK if app_db.backend_name() == "sqlite" else nullcontext()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode(record: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(record or {})
    data.pop("id", None)
    data.pop("tenant_id", None)
    for key in ("created_at", "updated_at"):
        data.pop(key, None)
    return data


def _decode(row: Any) -> Dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    raw = mapping["data"]
    try:
        payload = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        payload = {}
    out = dict(payload)
    out["id"] = mapping["id"]
    out["tenant_id"] = mapping["tenant_id"]
    out["created_at"] = mapping["created_at"]
    out["updated_at"] = mapping["updated_at"]
    if mapping["reference"] is not None:
        out["reference"] = mapping["reference"]
    if mapping["status"] is not None:
        out["status"] = mapping["status"]
    return out


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Insert one record for one tenant and return the stored row."""
    table = _table(entity)
    payload = _encode(record)
    now = _now()
    stmt = table.insert().values(
        tenant_id=str(tenant_id),
        reference=str(payload.get("reference") or "") or None,
        status=str(payload.get("status") or "") or None,
        data=json.dumps(payload, ensure_ascii=False, default=str),
        created_at=now,
        updated_at=now,
    )
    with _write_guard():
        with app_db.engine().begin() as conn:
            result = conn.execute(stmt)
            record_id = int(result.inserted_primary_key[0])
            row = conn.execute(
                select(table).where(and_(table.c.id == record_id, table.c.tenant_id == str(tenant_id)))
            ).first()
    if row is None:
        raise RuntimeError("stored record could not be read back")
    return _decode(row)


def get(entity: str, record_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    table = _table(entity)
    with app_db.engine().connect() as conn:
        row = conn.execute(
            select(table).where(
                and_(table.c.id == int(record_id), table.c.tenant_id == str(tenant_id))
            )
        ).first()
    return _decode(row) if row is not None else None


def list_all(entity: str, tenant_id: str) -> List[Dict[str, Any]]:
    table = _table(entity)
    with app_db.engine().connect() as conn:
        rows = conn.execute(
            select(table).where(table.c.tenant_id == str(tenant_id)).order_by(table.c.id)
        ).all()
    return [_decode(row) for row in rows]


def query(
    entity: str,
    tenant_id: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Tenant-scoped list with field filters applied to the JSON payload.

    The filter is applied in Python over the tenant's rows so the query
    statement stays a Core select with bound tenant and limit values; the
    result set is small by design (one client's operational records).
    """
    rows = list_all(entity, tenant_id)
    if filters:
        def matches(row: Dict[str, Any]) -> bool:
            return all(str(row.get(key)) == str(value) for key, value in filters.items())

        rows = [row for row in rows if matches(row)]
    return rows[: max(0, int(limit))]


def update(
    entity: str, record_id: int, changes: Dict[str, Any], tenant_id: str
) -> Optional[Dict[str, Any]]:
    table = _table(entity)
    current = get(entity, record_id, tenant_id)
    if current is None:
        return None
    payload = _encode(current)
    payload.update({k: v for k, v in (changes or {}).items() if k not in ("id", "tenant_id")})
    stmt = (
        sa_update(table)
        .where(and_(table.c.id == int(record_id), table.c.tenant_id == str(tenant_id)))
        .values(
            reference=str(payload.get("reference") or "") or None,
            status=str(payload.get("status") or "") or None,
            data=json.dumps(payload, ensure_ascii=False, default=str),
            updated_at=_now(),
        )
    )
    with _write_guard():
        with app_db.engine().begin() as conn:
            conn.execute(stmt)
    return get(entity, record_id, tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    table = _table(entity)
    stmt = sa_delete(table).where(
        and_(table.c.id == int(record_id), table.c.tenant_id == str(tenant_id))
    )
    with _write_guard():
        with app_db.engine().begin() as conn:
            result = conn.execute(stmt)
    return bool(result.rowcount)


def count(entity: str, tenant_id: str) -> int:
    return len(list_all(entity, tenant_id))


def enable_wal() -> None:
    """Switch a SQLite database to WAL once, at boot."""
    if app_db.backend_name() != "sqlite":
        return
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()
