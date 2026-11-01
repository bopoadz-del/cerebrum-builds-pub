"""Persistence for the domain models.

Statements are SQLAlchemy Core built from the declared schema
(COLUMNS), compiled for whichever backend app.db is on: the SQLite
file by default, Postgres when DATABASE_URL is set. No SQL text is
assembled from names; values always travel as bound parameters.
Schema is applied by Alembic (app/migrations.py + alembic/versions/),
never by this module.

Durability on SQLite: WAL + busy_timeout matched to the FastAPI sync
threadpool. One writer; readers proceed. STORAGE_PATH relocates the file
onto the mounted disk.

An entity's name IS its capability id -- the stem of its handler module,
the table alembic/versions/0001_baseline.py creates, and the name the
factory's one-record round-trip probe reads back.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite as _sqlite_dialect

from app import db as _db

from app.models import MODELS as _MODELS

#: The capability roster, taken from the one declaration the platform owns
#: (app.models.MODELS). A capability added to the models is persistable the
#: moment it is declared, and the migration's tables are exactly these names.
TABLES: Tuple[str, ...] = tuple(sorted(_MODELS))

#: The declared columns per entity -- the model's own FIELDS, in order.
COLUMNS: Dict[str, List[str]] = {
    cap: list(getattr(cls, "FIELDS", []) or []) for cap, cls in sorted(_MODELS.items())
}

#: The one persistence root this platform reads. app.db resolves it
#: (SQLite under STORAGE_PATH; Postgres when DATABASE_URL is set).
STORAGE_PATH_ENV = "STORAGE_PATH"

SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_CONNECT_TIMEOUT_S = 30.0
FASTAPI_SYNC_THREADPOOL = 40

_SQLITE = _sqlite_dialect.dialect(paramstyle="qmark")

#: SQLite allows one writer at a time. The stdlib driver's busy handler can
#: spin for a very long time when many threads open DEFERRED transactions on
#: a network/overlay filesystem, so writers in this process queue here and
#: take the write lock in a defined order. Postgres has real row locking and
#: does not use this gate.
_WRITE_LOCK = threading.RLock()


def _write_guard() -> Any:
    """A no-op for Postgres; the process write lock for SQLite."""
    if _db.is_postgres():
        import contextlib

        return contextlib.nullcontext()
    return _WRITE_LOCK


class QueryError(ValueError):
    """A caller asked for an entity, column or ordering that is not declared."""


def _table(entity: str) -> Any:
    """The declared table. An undeclared entity is refused, never named."""
    if entity not in COLUMNS:
        raise QueryError("unknown entity: " + str(entity))
    names = ["id", "tenant_id", *COLUMNS[entity]]
    return sa.table(entity, *(sa.column(n) for n in dict.fromkeys(names)))


def db_path() -> Path:
    """The SQLite file app.db uses when DATABASE_URL is unset."""
    return _db.sqlite_path()


def connect() -> Any:
    """A connection from app.db -- the one place that decides the backend.

    This module never opens a database of its own: a store that did wrote
    SQLite while DATABASE_URL said Postgres. app.db sets the per-connection
    pragmas (busy_timeout) and does NOT switch journal_mode per connection
    -- WAL is set once at boot.
    """
    return _db.connect()


def enable_wal() -> None:
    """Switch the SQLite file to WAL once, single-threaded, at boot.

    WAL then persists in the file, so later connections inherit it without a
    mode switch of their own. Postgres has no journal mode.
    """
    if _db.is_postgres():
        return
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def _connect() -> Any:
    return connect()


def _execute(conn: Any, statement: Any) -> Any:
    """Run one Core statement on either backend's connection."""
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
    with _write_guard():
        conn = _connect()
        try:
            if _db.is_postgres():
                row_id = int(_execute(conn, statement.returning(table.c.id)).scalar_one())
            else:
                row_id = int(_execute(conn, statement).lastrowid)
            conn.commit()
        finally:
            conn.close()
    return {"id": row_id, "tenant_id": tenant_id, **{c: record.get(c) for c in cols}}


def list_all(entity: str, tenant_id: str | None = None) -> List[Dict[str, Any]]:
    """Rows for one tenant, oldest id first.

    ``tenant_id`` is the principal's tenant and callers pass it explicitly;
    an omitted tenant resolves to the platform tenant rather than reading
    every tenant's rows -- the one-record round-trip probe re-reads a record
    it just POSTed as ``store.list_all(entity)``.
    """
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

    Columns are resolved against the declared table, never interpolated from
    caller input: an unknown field raises QueryError instead of reaching SQL.
    Values always travel as bound parameters.
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


def _conditions(
    entity: str,
    tenant_id: str,
    filters: Dict[str, Any] | None,
    any_of: Dict[str, Sequence[Any]] | None,
) -> Tuple[Any, List[Any]]:
    """The declared table and the WHERE terms for one tenant's rows.

    Column names are resolved against COLUMNS, so an undeclared one raises
    QueryError instead of reaching SQL; every value is a bound parameter.
    A set membership is expressed as an OR of equalities: each value is then
    one bound parameter on every backend, which keeps the compiled statement
    portable (sqlite's qmark dialect expands an IN (...) list at
    post-compile time, and _execute binds one parameter per value).
    """
    table = _table(entity)
    cols = COLUMNS[entity]
    conditions: List[Any] = [table.c.tenant_id == tenant_id]
    for name, value in (filters or {}).items():
        if name not in cols:
            raise QueryError("unknown filter field: " + str(name))
        conditions.append(table.c[name] == value)
    for name, values in (any_of or {}).items():
        if name not in cols:
            raise QueryError("unknown filter field: " + str(name))
        wanted = list(values or [])
        if not wanted:
            continue
        conditions.append(sa.or_(*[table.c[name] == value for value in wanted]))
    return table, conditions


def count(
    entity: str,
    tenant_id: str,
    *,
    filters: Dict[str, Any] | None = None,
    any_of: Dict[str, Sequence[Any]] | None = None,
) -> int:
    """Rows of one entity for one tenant, counted on the declared schema."""
    table, conditions = _conditions(entity, tenant_id, filters, any_of)
    statement = sa.select(sa.func.count()).select_from(table).where(*conditions)
    conn = _connect()
    try:
        return int(_execute(conn, statement).fetchone()[0])
    finally:
        conn.close()


def total(
    entity: str,
    tenant_id: str,
    column: str,
    *,
    filters: Dict[str, Any] | None = None,
    any_of: Dict[str, Sequence[Any]] | None = None,
    multiply_by: str | None = None,
) -> float:
    """Sum one declared column (optionally column x column) for one tenant.

    ``total("invoicing_tunisian_vat", tenant, "unit_price_ht",
    multiply_by="quantity", any_of={"payment_state": ["paid"]})`` is the
    net-of-VAT value of the tenant's paid invoices, computed by the backend
    over bound parameters -- never by reading rows into the application.
    """
    cols = COLUMNS[entity]
    if column not in cols:
        raise QueryError("unknown total column: " + str(column))
    if multiply_by is not None and multiply_by not in cols:
        raise QueryError("unknown total column: " + str(multiply_by))
    table, conditions = _conditions(entity, tenant_id, filters, any_of)
    expression = table.c[column]
    if multiply_by is not None:
        expression = expression * table.c[multiply_by]
    statement = sa.select(
        sa.func.coalesce(sa.func.sum(expression), 0)
    ).select_from(table).where(*conditions)
    conn = _connect()
    try:
        value = _execute(conn, statement).fetchone()[0]
    finally:
        conn.close()
    return float(value or 0.0)


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
    with _write_guard():
        conn = _connect()
        try:
            changed = _execute(conn, statement).rowcount
            conn.commit()
        finally:
            conn.close()
    if changed == 0:
        return None
    return get(entity, record_id, tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    """Delete a persisted row. True when a row was removed."""
    table = _table(entity)
    statement = sa.delete(table).where(
        table.c.id == record_id, table.c.tenant_id == tenant_id
    )
    with _write_guard():
        conn = _connect()
        try:
            removed = _execute(conn, statement).rowcount
            conn.commit()
        finally:
            conn.close()
    return removed > 0
