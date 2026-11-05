"""Tenant-scoped persistence over the one database app.db decides.

There is exactly one persistence root -- STORAGE_PATH -- and one file decision
made in app.db; this module never opens a database of its own. The schema
belongs to Alembic (one ``op.create_table`` per entity); this
module only reads and writes through SQLAlchemy Core statements built from the
declared columns, with every value bound as a parameter. Every call takes an
explicit ``tenant_id`` -- there is no default tenant in the store, because a
default is how a cross-tenant read becomes invisible.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete as _delete,
    select as _select,
    update as _update,
)

from app import config, db
from app.models import MODELS

SQLITE_BUSY_TIMEOUT_MS = db.SQLITE_BUSY_TIMEOUT_MS

#: The one persistence root. app.db resolves the file inside it; nothing else
#: opens a database, and a second root is a defect the floor refuses.
STORAGE_PATH_ENV = "STORAGE_PATH"

#: The sync threadpool the service runs request bodies on; the concurrency
#: drill drives at least this many simultaneous writes.
FASTAPI_SYNC_THREADPOOL = config.sync_threadpool()

#: Internal tables that are not capabilities: the kernel's queue, its
#: idempotency ledger, and the lifecycle audit.
INTERNAL_COLUMNS: Dict[str, List[str]] = {
    "work_queue": ["capability_id", "payload", "status", "attempts", "result", "idempotency_key"],
    "idempotency": ["idempotency_key", "entity", "record_id"],
    "lifecycle_audit": ["entity", "record_id", "action", "detail"],
    "rag_documents": ["source", "title", "text", "authority", "chunk_count"],
    "rag_chunks": ["document_id", "ordinal", "text"],
}

#: entity -> the domain columns that entity carries (id/tenant_id/timestamps
#: are platform columns and are added by _table()).
COLUMNS: Dict[str, List[str]] = {
    name: list(cls.FIELDS) for name, cls in MODELS.items()
}
COLUMNS.update({name: list(cols) for name, cols in INTERNAL_COLUMNS.items()})

_META = MetaData()
_TABLES: Dict[str, Table] = {}
_TABLE_LOCK = threading.Lock()
#: SQLite admits ONE writer at a time. Letting N request threads race for the
#: file's write lock means N-1 of them hold a pooled connection while they
#: wait, and once N exceeds the pool every waiting thread is also holding the
#: connection the writer would need to finish: the writes time out and the
#: pool reports a checkout timeout. The platform serialises the write
#: transaction itself on SQLite (docs/data_lifecycle.json declares writers: 1),
#: so a waiting writer holds no connection; Postgres keeps real concurrency.
_WRITE_LOCK = threading.Lock()


@contextmanager
def _write_transaction():
    """Hold the platform's single-writer seat for a SQLite write.

    Postgres is left alone: its MVCC writers do not contend for one file lock.
    """
    if db.backend_name() == "sqlite":
        with _WRITE_LOCK:
            yield
    else:
        yield


def storage_root() -> Path:
    """The declared persistence root (STORAGE_PATH), resolved like app.db does."""
    declared = os.environ.get(STORAGE_PATH_ENV)
    return Path(declared) if declared else config.storage_root()


def db_path():
    """The SQLite file this process owns (None on Postgres)."""
    return db.sqlite_path()


def connect():
    """A live connection to the backend, from app.db only (# no own engine)."""
    return db.connect()


def entity_columns(entity: str) -> List[str]:
    if entity not in COLUMNS:
        raise KeyError(f"unknown entity: {entity}")
    return list(COLUMNS[entity])


def _table(entity: str) -> Table:
    with _TABLE_LOCK:
        table = _TABLES.get(entity)
        if table is not None:
            return table
        columns = entity_columns(entity)
        cols: List[Any] = [
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("tenant_id", String(120), nullable=False, index=True),
            Column("created_at", String(40)),
            Column("updated_at", String(40)),
        ]
        for name in columns:
            cols.append(Column(name, Text))
        table = Table(entity, _META, *cols, extend_existing=True)
        _TABLES[entity] = table
        return table


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str)
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return json.dumps(str(value))


def _decode(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _row(entity: str, row: Any) -> Dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    out: Dict[str, Any] = {"id": mapping["id"]}
    for name in entity_columns(entity):
        out[name] = _decode(mapping[name])
    out["tenant_id"] = mapping["tenant_id"]
    out["created_at"] = mapping["created_at"]
    out["updated_at"] = mapping["updated_at"] if "updated_at" in mapping.keys() else None
    return out


def _values(entity: str, record: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise TypeError("a record must be a mapping")
    return {
        name: _encode(record.get(name))
        for name in entity_columns(entity)
        if name in record
    }


def _require_tenant(tenant_id: Optional[str]) -> str:
    value = str(tenant_id or "").strip()
    if not value:
        raise ValueError("a tenant_id is required: the store has no default tenant")
    return value


def save(entity: str, record: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
    tenant = _require_tenant(tenant_id)
    table = _table(entity)
    values = _values(entity, record)
    values["tenant_id"] = tenant
    values["created_at"] = _now()
    engine = db.engine()
    with _write_transaction(), engine.begin() as conn:
        result = conn.execute(table.insert().values(**values))
        new_id = result.inserted_primary_key[0]
        # Read the stored row back on the SAME connection. A read-back on a
        # second pooled connection turns every save into a hold-and-wait:
        # N concurrent saves each pin one connection while queueing for
        # another, and once N exceeds the pool the writes that wait on the
        # pool never release the ones the pool is waiting for. The row is
        # read inside the write's own transaction, so a saved record is
        # visible to the caller that saved it and to nobody else first.
        written = conn.execute(
            _select(table).where(table.c.id == new_id).where(table.c.tenant_id == tenant)
        ).first()
    stored = _row(entity, written) if written is not None else None
    if stored is None:
        raise RuntimeError(f"{entity} save did not read back")
    return stored


def get(entity: str, record_id: Any, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    tenant = _require_tenant(tenant_id)
    try:
        key = int(record_id)
    except (TypeError, ValueError):
        return None
    table = _table(entity)
    statement = _select(table).where(table.c.id == key).where(table.c.tenant_id == tenant)
    engine = db.engine()
    with engine.connect() as conn:
        row = conn.execute(statement).first()
    return _row(entity, row) if row is not None else None


def list_all(entity: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    tenant = _require_tenant(tenant_id)
    table = _table(entity)
    statement = _select(table).where(table.c.tenant_id == tenant).order_by(table.c.id)
    engine = db.engine()
    with engine.connect() as conn:
        rows = conn.execute(statement).fetchall()
    return [_row(entity, row) for row in rows]


def update(entity: str, record_id: Any, record: Dict[str, Any], tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    tenant = _require_tenant(tenant_id)
    table = _table(entity)
    try:
        key = int(record_id)
    except (TypeError, ValueError):
        return None
    values = _values(entity, record)
    values["updated_at"] = _now()
    engine = db.engine()
    with _write_transaction(), engine.begin() as conn:
        conn.execute(
            _update(table)
            .where(table.c.id == key)
            .where(table.c.tenant_id == tenant)
            .values(**values)
        )
        written = conn.execute(
            _select(table).where(table.c.id == key).where(table.c.tenant_id == tenant)
        ).first()
    return _row(entity, written) if written is not None else None


def delete(entity: str, record_id: Any, tenant_id: Optional[str] = None) -> bool:
    tenant = _require_tenant(tenant_id)
    table = _table(entity)
    try:
        key = int(record_id)
    except (TypeError, ValueError):
        return False
    engine = db.engine()
    with _write_transaction(), engine.begin() as conn:
        result = conn.execute(
            _delete(table).where(table.c.id == key).where(table.c.tenant_id == tenant)
        )
    return bool(result.rowcount)


def count(entity: str, tenant_id: str) -> int:
    return len(list_all(entity, tenant_id=tenant_id))


def entities() -> Iterable[str]:
    return tuple(COLUMNS)
