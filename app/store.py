"""Tenant-scoped persistence over one storage root.

The schema belongs to alembic (alembic/versions/0001_baseline.py); this
module never issues DDL. Every statement is a SQLAlchemy Core construct over
table/column objects with bound parameters -- no string-built SQL ever
reaches an execute() call.

The database itself is decided by app.db (DATABASE_URL means Postgres, else
the SQLite file under STORAGE_PATH); this module takes its connection from
there and opens no database of its own.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    delete as sql_delete,
    insert as sql_insert,
    select as sql_select,
    update as sql_update,
)
from sqlalchemy.exc import OperationalError

from app import db as app_db
from app import models as app_models

#: How long a SQLite connection waits for the write lock. Set on every
#: connection by app.db, and exported here because the operator tunes it.
SQLITE_BUSY_TIMEOUT_MS = app_db.SQLITE_BUSY_TIMEOUT_MS

#: Blocking handlers run in Starlette's sync threadpool; the concurrency
#: budget the persistence path is measured against is at least this large.
FASTAPI_SYNC_THREADPOOL = int(os.environ.get("FASTAPI_SYNC_THREADPOOL") or 40)

#: SQLite stores ids as signed 64-bit integers; anything outside is not a row.
MAX_RECORD_ID = 2**63 - 1
MIN_RECORD_ID = 1

RETRY_ATTEMPTS = 5
RETRY_BACKOFF_S = 0.05

_METADATA = MetaData()
_TABLES: Dict[str, Table] = {}
_TABLE_LOCK = threading.RLock()

_NUMERIC = {"int", "float"}
_TYPES = {
    "int": Integer,
    "float": Float,
    "bool": Boolean,
    "str": String,
    "date": String,
    "datetime": String,
}

#: The declared columns per entity, derived from the same models the routes
#: validate against. The alembic baseline creates exactly these.
COLUMNS: Dict[str, Dict[str, str]] = {}
for _entity, _model in app_models.MODELS.items():
    COLUMNS[_entity] = {
        name: str((_model.CONSTRAINTS.get(name) or {}).get("type") or "str")
        for name in _model.FIELDS
    }

#: Platform-owned entities that are not customer capabilities: the work
#: queue the kernel S12 outcomes drive, its idempotency ledger, and the
#: lifecycle audit 0002 adds. Same store, same tenant scoping.
COLUMNS["work_queue"] = {
    "capability_id": "str",
    "payload": "str",
    "status": "str",
    "idempotency_key": "str",
    "result": "str",
}
COLUMNS["idempotency"] = {
    "key": "str",
    "entity": "str",
    "record_id": "int",
}
COLUMNS["lifecycle_audit"] = {
    "entity": "str",
    "revision": "str",
    "detail": "str",
}


STORAGE_PATH_ENV = "STORAGE_PATH"


def storage_path_env() -> str:
    return os.environ.get("STORAGE_PATH") or ""


def db_path():
    """The SQLite file this platform keeps its rows in (STORAGE_PATH root)."""
    return app_db.sqlite_path()


def enable_wal() -> None:
    """Switch the SQLite file to WAL once, at boot, before traffic."""
    if app_db.backend_name() != "sqlite":
        return
    conn = app_db.connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def connect():
    """A DBAPI connection from app.db (health probes through this)."""
    return app_db.connect()


def valid_id(record_id: Any) -> bool:
    try:
        value = int(record_id)
    except (TypeError, ValueError):
        return False
    return MIN_RECORD_ID <= value <= MAX_RECORD_ID


def _table(entity: str) -> Table:
    name = str(entity)
    with _TABLE_LOCK:
        table = _TABLES.get(name)
        if table is not None:
            return table
        columns = COLUMNS.get(name)
        if columns is None:
            raise KeyError(f"unknown entity: {name}")
        cols = [
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("tenant_id", String, nullable=False),
        ]
        for field, kind in columns.items():
            cols.append(Column(field, _TYPES.get(kind, String)))
        cols.extend(
            [
                Column("created_at", String),
                Column("updated_at", String),
            ]
        )
        table = Table(name, _METADATA, *cols, extend_existing=True)
        _TABLES[name] = table
        return table


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _coerce(kind: str, value: Any) -> Any:
    if value is None:
        return None
    if kind == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if kind == "bool":
        return bool(value)
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _with_retry(operation):
    last: Optional[Exception] = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return operation()
        except OperationalError as exc:  # a busy database is transient
            last = exc
            if attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_BACKOFF_S * (2**attempt))
    raise last  # pragma: no cover - unreachable


def _row_to_dict(table: Table, row) -> Dict[str, Any]:
    mapping = row._mapping
    out: Dict[str, Any] = {}
    for column in table.columns:
        out[column.name] = mapping[column.name]
    return out


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Insert one record for one tenant and return it with its id."""
    table = _table(entity)
    data = dict(record or {})
    values: Dict[str, Any] = {"tenant_id": str(tenant_id or "local")}
    for field, kind in COLUMNS[str(entity)].items():
        if field in data:
            values[field] = _coerce(kind, data[field])
    stamp = _now()
    values["created_at"] = stamp
    values["updated_at"] = stamp

    def _insert():
        with app_db.engine().begin() as conn:
            result = conn.execute(sql_insert(table).values(**values))
            new_id = result.inserted_primary_key[0]
            row = conn.execute(
                sql_select(table).where(
                    (table.c.id == new_id) & (table.c.tenant_id == values["tenant_id"])
                )
            ).first()
            return _row_to_dict(table, row)

    return _with_retry(_insert)


def get(entity: str, record_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    if not valid_id(record_id):
        return None
    table = _table(entity)

    def _get():
        with app_db.engine().connect() as conn:
            row = conn.execute(
                sql_select(table).where(
                    (table.c.id == int(record_id))
                    & (table.c.tenant_id == str(tenant_id or "local"))
                )
            ).first()
            return _row_to_dict(table, row) if row is not None else None

    return _with_retry(_get)


def list_all(entity: str, tenant_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    table = _table(entity)

    def _list():
        with app_db.engine().connect() as conn:
            rows = conn.execute(
                sql_select(table)
                .where(table.c.tenant_id == str(tenant_id or "local"))
                .order_by(table.c.id.asc())
                .limit(int(limit))
            ).all()
            return [_row_to_dict(table, row) for row in rows]

    return _with_retry(_list)


def query(entity: str, tenant_id: str, **filters: Any) -> List[Dict[str, Any]]:
    """Rows for one tenant matching equality filters on declared columns.

    Column names come from the declared table, never from the caller's text;
    values travel as bound parameters.
    """
    table = _table(entity)
    clauses = [table.c.tenant_id == str(tenant_id or "local")]
    for name, value in filters.items():
        column = table.c.get(str(name))
        if column is None or value in (None, ""):
            continue
        clauses.append(column == value)

    def _query():
        with app_db.engine().connect() as conn:
            statement = sql_select(table).where(*clauses).order_by(table.c.id.asc())
            return [_row_to_dict(table, row) for row in conn.execute(statement).all()]

    return _with_retry(_query)


def update(
    entity: str, record_id: int, record: Dict[str, Any], tenant_id: str
) -> Optional[Dict[str, Any]]:
    if not valid_id(record_id):
        return None
    table = _table(entity)
    data = dict(record or {})
    values: Dict[str, Any] = {"updated_at": _now()}
    for field, kind in COLUMNS[str(entity)].items():
        if field in data:
            values[field] = _coerce(kind, data[field])

    def _update():
        with app_db.engine().begin() as conn:
            conn.execute(
                sql_update(table)
                .where(
                    (table.c.id == int(record_id))
                    & (table.c.tenant_id == str(tenant_id or "local"))
                )
                .values(**values)
            )
            row = conn.execute(
                sql_select(table).where(
                    (table.c.id == int(record_id))
                    & (table.c.tenant_id == str(tenant_id or "local"))
                )
            ).first()
            return _row_to_dict(table, row) if row is not None else None

    return _with_retry(_update)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    if not valid_id(record_id):
        return False
    table = _table(entity)

    def _delete():
        with app_db.engine().begin() as conn:
            result = conn.execute(
                sql_delete(table).where(
                    (table.c.id == int(record_id))
                    & (table.c.tenant_id == str(tenant_id or "local"))
                )
            )
            return bool(result.rowcount)

    return _with_retry(_delete)


def count(entity: str, tenant_id: str) -> int:
    return len(list_all(entity, tenant_id))


def entities() -> Iterable[str]:
    return tuple(COLUMNS)
