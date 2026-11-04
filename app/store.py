"""Tenant-scoped persistence over the database ``app.db`` decides.

Schema is alembic's: this module never issues CREATE TABLE.  Every entity
carries its records as a JSON payload beside the tenant and identifier, so a
field added to a model does not need a migration to survive a round trip.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete as sa_delete,
    insert,
    select,
    update as sa_update,
)

from app import db as _db
from app.models import ENTITY_NAMES, MODELS

DB_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = 30000
FASTAPI_SYNC_THREADPOOL = 40

_metadata = MetaData()

_TABLES: Dict[str, Table] = {}

COLUMNS: Dict[str, List[str]] = {
    name: ["id", "tenant_id", "created_at", "payload"] for name in ENTITY_NAMES
}


def _table(entity: str) -> Table:
    name = str(entity)
    if name not in _TABLES:
        if name not in ENTITY_NAMES:
            raise KeyError("unknown entity: %s" % name)
        _TABLES[name] = Table(
            name,
            _metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("tenant_id", String(128), nullable=False, index=True),
            Column("created_at", String(40), nullable=False),
            Column("payload", Text, nullable=False),
        )
    return _TABLES[name]


def enable_wal() -> None:
    """Set WAL once, at boot; never per connection (that races)."""
    if _db.backend_name() != "sqlite":
        return
    conn = _db.connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def db_path():
    return _db.sqlite_path()


def connect():
    return _db.connect()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(record: Dict[str, Any], row_id: Any, tenant_id: str) -> Dict[str, Any]:
    out = dict(record)
    out["id"] = int(row_id) if row_id is not None else None
    out["tenant_id"] = tenant_id
    return out


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Insert one record, returning it with the store's own identifier."""
    if not tenant_id:
        raise ValueError("tenant_id is required: a record is never tenantless")
    table = _table(entity)
    payload = dict(record or {})
    payload.pop("id", None)
    payload.pop("tenant_id", None)
    values = {
        "tenant_id": str(tenant_id),
        "created_at": _now(),
        "payload": json.dumps(payload, sort_keys=True, default=str),
    }
    with _db.engine().begin() as conn:
        stmt = insert(table).values(**values)
        if _db.backend_name() == "postgres":
            row_id = conn.execute(stmt.returning(table.c.id)).scalar_one()
        else:
            result = conn.execute(stmt)
            row_id = getattr(result, "lastrowid", None)
            if row_id is None:
                keys = list(getattr(result, "inserted_primary_key", []) or [])
                row_id = keys[0] if keys else None
    return _row(payload, row_id, str(tenant_id))


def get(entity: str, record_id: Any, tenant_id: str) -> Optional[Dict[str, Any]]:
    if not tenant_id:
        raise ValueError("tenant_id is required: a record is never tenantless")
    table = _table(entity)
    try:
        key = int(record_id)
    except (TypeError, ValueError):
        return None
    with _db.engine().connect() as conn:
        row = conn.execute(
            select(table.c.payload, table.c.id).where(
                table.c.id == key, table.c.tenant_id == str(tenant_id)
            )
        ).first()
    if row is None:
        return None
    return _row(json.loads(row[0]), row[1], str(tenant_id))


def list_all(entity: str, tenant_id: str) -> List[Dict[str, Any]]:
    if not tenant_id:
        raise ValueError("tenant_id is required: a list is never tenantless")
    table = _table(entity)
    with _db.engine().connect() as conn:
        rows = conn.execute(
            select(table.c.payload, table.c.id)
            .where(table.c.tenant_id == str(tenant_id))
            .order_by(table.c.id)
        ).all()
    return [_row(json.loads(payload), row_id, str(tenant_id)) for payload, row_id in rows]


def update(entity: str, record_id: Any, record: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    current = get(entity, record_id, tenant_id)
    if current is None:
        return None
    table = _table(entity)
    payload = dict(record or {})
    payload.pop("id", None)
    payload.pop("tenant_id", None)
    with _db.engine().begin() as conn:
        conn.execute(
            sa_update(table)
            .where(table.c.id == int(record_id), table.c.tenant_id == str(tenant_id))
            .values(payload=json.dumps(payload, sort_keys=True, default=str))
        )
    return _row(payload, int(record_id), str(tenant_id))


def delete(entity: str, record_id: Any, tenant_id: str) -> bool:
    table = _table(entity)
    try:
        key = int(record_id)
    except (TypeError, ValueError):
        return False
    with _db.engine().begin() as conn:
        result = conn.execute(
            sa_delete(table).where(table.c.id == key, table.c.tenant_id == str(tenant_id))
        )
    return bool(result.rowcount)


def search(entity: str, needle: str, tenant_id: str) -> List[Dict[str, Any]]:
    text = str(needle or "").strip().lower()
    if not text:
        return list_all(entity, tenant_id)
    return [
        row for row in list_all(entity, tenant_id)
        if text in json.dumps(row, sort_keys=True, default=str).lower()
    ]


#: The model that declares each entity, for callers that only hold the name.
MODEL_BY_ENTITY = {cls.ENTITY: cls for cls in MODELS.values()}
