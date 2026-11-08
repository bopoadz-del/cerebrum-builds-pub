"""Persistence for the domain models.

Statements are SQLAlchemy Core built from the declared schema (COLUMNS) and
compiled for whichever backend app.db is on: the SQLite file by default,
Postgres when DATABASE_URL is set. No SQL text is assembled from names;
values always travel as bound parameters.

Schema is applied by Alembic (app/migrations.py + alembic/versions/), never
by this module: connect() does NOT create a table.

An entity's name IS its capability id -- the stem of its handler module,
the table alembic/versions/0001_baseline.py creates, and the name the
factory's one-record round-trip probe reads back.

Scope READS: the configured database.
Scope WRITES: rows of the declared entities.
Scope NEVER: no network, no second database, no DDL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite as _sqlite_dialect

from app import db as _db
from app.models import MODELS as _MODELS

TABLES: Tuple[str, ...] = tuple(sorted(_MODELS))

COLUMNS: Dict[str, List[str]] = {
    cap: list(getattr(cls, "FIELDS", []) or []) for cap, cls in sorted(_MODELS.items())
}

STORAGE_PATH_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_CONNECT_TIMEOUT_S = 30.0
FASTAPI_SYNC_THREADPOOL = 40

_SQLITE = _sqlite_dialect.dialect(paramstyle="qmark")


class QueryError(ValueError):
    """A caller asked for an entity, column or ordering that is not declared."""


def _table(entity: str) -> Any:
    if entity not in COLUMNS:
        raise QueryError("unknown entity: " + str(entity))
    names = ["id", "tenant_id", *COLUMNS[entity]]
    return sa.table(entity, *(sa.column(n) for n in dict.fromkeys(names)))


def db_path() -> Path:
    return _db.sqlite_path()


def connect() -> Any:
    """A connection from app.db -- the one place that decides the backend."""
    return _db.connect()


def enable_wal() -> None:
    """Switch the SQLite file to WAL once, single-threaded, at boot."""
    if _db.is_postgres():
        return
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def _execute(conn: Any, statement: Any) -> Any:
    if _db.is_postgres():
        return conn.execute(statement)
    compiled = statement.compile(dialect=_SQLITE)
    params = [compiled.params[name] for name in (compiled.positiontup or ())]
    return conn.execute(str(compiled), params)


def _as_dict(row: Any) -> Dict[str, Any]:
    mapping = getattr(row, "_mapping", None)
    return dict(mapping) if mapping is not None else dict(row)


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Insert a record for one tenant and return it with its assigned id."""
    table = _table(entity)
    cols = COLUMNS[entity]
    values = {"tenant_id": tenant_id, **{c: record.get(c) for c in cols}}
    statement = sa.insert(table).values(**values)
    conn = _connect()
    try:
        if _db.is_postgres():
            row_id = int(_execute(conn, statement.returning(table.c.id)).scalar_one())
        else:
            row_id = int(_execute(conn, statement).lastrowid)
        conn.commit()
        return {"id": row_id, "tenant_id": tenant_id, **{c: record.get(c) for c in cols}}
    finally:
        conn.close()


def list_all(entity: str, tenant_id: str | None = None) -> List[Dict[str, Any]]:
    """Rows for one tenant, oldest id first."""
    if tenant_id is None:
        from app.tenancy import DEFAULT_TENANT

        tenant_id = DEFAULT_TENANT
    table = _table(entity)
    statement = sa.select(table).where(table.c.tenant_id == tenant_id).order_by(table.c.id)
    conn = _connect()
    try:
        return [_as_dict(r) for r in _execute(conn, statement).fetchall()]
    finally:
        conn.close()


def query(
    entity: str,
    tenant_id: str,
    *,
    filters: Dict[str, Any] | None = None,
    sort: str | None = None,
    order: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Filter, sort and page one entity.

    Column names are resolved against the declared table, never interpolated
    from caller input; values travel as bound parameters.
    """
    table = _table(entity)
    cols = COLUMNS[entity]
    conditions = [table.c.tenant_id == tenant_id]
    for name, value in (filters or {}).items():
        if name not in cols:
            raise QueryError("unknown filter field: " + str(name))
        conditions.append(table.c[name] == value)
    if sort is not None and sort not in cols and sort != "id":
        raise QueryError("unknown sort field: " + str(sort))
    direction = str(order or "asc").lower()
    if direction not in ("asc", "desc"):
        raise QueryError("order must be asc or desc")
    if limit < 1 or limit > 500:
        raise QueryError("limit must be between 1 and 500")
    if offset < 0:
        raise QueryError("offset must be >= 0")
    column = table.c[sort or "id"]
    ordering = column.desc() if direction == "desc" else column.asc()
    counted = sa.select(sa.func.count()).select_from(table).where(*conditions)
    page = (
        sa.select(table).where(*conditions).order_by(ordering).limit(limit).offset(offset)
    )
    conn = _connect()
    try:
        total = int(_execute(conn, counted).fetchone()[0])
        rows = _execute(conn, page).fetchall()
        return {
            "items": [_as_dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


def get(entity: str, record_id: int, tenant_id: str) -> Dict[str, Any] | None:
    table = _table(entity)
    statement = sa.select(table).where(
        table.c.id == record_id, table.c.tenant_id == tenant_id
    )
    conn = _connect()
    try:
        row = _execute(conn, statement).fetchone()
        return _as_dict(row) if row else None
    finally:
        conn.close()


def update(entity: str, record_id: int, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any] | None:
    """Overwrite a persisted row. Returns None when the id does not exist."""
    table = _table(entity)
    statement = (
        sa.update(table)
        .where(table.c.id == record_id, table.c.tenant_id == tenant_id)
        .values(**{c: record.get(c) for c in COLUMNS[entity]})
    )
    conn = _connect()
    try:
        changed = _execute(conn, statement).rowcount
        conn.commit()
        if changed == 0:
            return None
    finally:
        conn.close()
    return get(entity, record_id, tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    """Delete a persisted row. True when a row was removed."""
    table = _table(entity)
    statement = sa.delete(table).where(
        table.c.id == record_id, table.c.tenant_id == tenant_id
    )
    conn = _connect()
    try:
        removed = _execute(conn, statement).rowcount
        conn.commit()
        return removed > 0
    finally:
        conn.close()


def _connect() -> Any:
    return connect()
