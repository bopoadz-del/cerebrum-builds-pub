"""Tenant-scoped persistence over the one database app.db decides.

The schema belongs to alembic; ``connect()`` sets a busy timeout and never
issues CREATE TABLE.  Column names come only from the declared models, and
every value travels as a bound parameter.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator, List, Optional

from app import db
from app.models import MODELS, SERVICE_SUBURB_COLUMNS, SERVICE_SUBURB_ENTITY

STORAGE_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = db.SQLITE_BUSY_TIMEOUT_MS
FASTAPI_SYNC_THREADPOOL = 40

COLUMNS: Dict[str, List[str]] = {
    entity: list(getattr(model, "FIELDS", []) or [])
    for entity, model in MODELS.items()
}
# The ops-maintained suburb catalogue is a supporting entity, not a
# capability: it has its own migration table and store columns but no route
# of its own (the ops back office maintains it).
COLUMNS[SERVICE_SUBURB_ENTITY] = list(SERVICE_SUBURB_COLUMNS)

_WRITE_LOCK = threading.RLock()


@contextmanager
def guard_writes() -> Iterator[None]:
    """Hold the store's write lock across a read-check-write sequence.

    Re-entrant, so save()/get() inside the guarded block still work.  Used
    by the booking route so a conflict check and the save it protects cannot
    interleave with another booking.
    """
    with _WRITE_LOCK:
        yield


def db_path():
    return db.sqlite_path()


def connect():
    return db.connect()


def enable_wal() -> None:
    """Switch the SQLite file to WAL once, from the boot path."""
    if db.backend_name() != "sqlite":
        return
    conn = db.connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    finally:
        conn.close()


def _identifier(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError("refusing a column name that is not declared: %r" % (name,))
    return '"' + name + '"'


def _ph() -> str:
    return "%s" if db.backend_name() == "postgres" else "?"


def _columns(entity: str) -> List[str]:
    try:
        return COLUMNS[entity]
    except KeyError:
        raise KeyError("unknown entity: %r" % (entity,)) from None


def _insert_sql(entity: str) -> str:
    cols = ["tenant_id", "created_at"] + _columns(entity)
    marks = [_ph() for _ in cols]
    return " ".join([
        "INSERT INTO", _identifier(entity), "(",
        ", ".join(_identifier(c) for c in cols), ")",
        "VALUES (", ", ".join(marks), ")",
    ])


def _select_all_sql(entity: str) -> str:
    return " ".join([
        "SELECT * FROM", _identifier(entity), "WHERE", _identifier("tenant_id"), "=", _ph(),
        "ORDER BY", _identifier("id"), "ASC",
    ])


def _select_one_sql(entity: str) -> str:
    return " ".join([
        "SELECT * FROM", _identifier(entity),
        "WHERE", _identifier("id"), "=", _ph(),
        "AND", _identifier("tenant_id"), "=", _ph(),
    ])


def _row(record: Any) -> Dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)
    return {key: record[key] for key in record.keys()}


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    cols = _columns(entity)
    now = _now()
    values: List[Any] = [str(tenant_id), now] + [record.get(c) for c in cols]
    with _WRITE_LOCK:
        conn = db.shared()
        cur = conn.execute(_insert_sql(entity), values)
        conn.commit()
        new_id = getattr(cur, "lastrowid", None)
        if new_id is None:
            fetched = conn.execute(
                " ".join([
                    "SELECT", _identifier("id"), "FROM", _identifier(entity),
                    "WHERE", _identifier("tenant_id"), "=", _ph(),
                    "ORDER BY", _identifier("id"), "DESC LIMIT 1",
                ]),
                [str(tenant_id)],
            ).fetchone()
            new_id = fetched[0] if fetched else None
    out = dict(record)
    out["id"] = new_id
    out["tenant_id"] = str(tenant_id)
    out["created_at"] = now
    return out


def get(entity: str, record_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    with _WRITE_LOCK:
        conn = db.shared()
        row = conn.execute(_select_one_sql(entity), [record_id, str(tenant_id)]).fetchone()
    return _row(row) if row is not None else None


def list_all(entity: str, tenant_id: str) -> List[Dict[str, Any]]:
    with _WRITE_LOCK:
        conn = db.shared()
        rows = conn.execute(_select_all_sql(entity), [str(tenant_id)]).fetchall()
    return [_row(row) for row in rows]


def query(
    entity: str,
    filters: Optional[Dict[str, Any]] = None,
    tenant_id: str = "",
    order_by: str = "id",
) -> List[Dict[str, Any]]:
    cols = _columns(entity)
    if order_by not in cols and order_by not in ("id", "created_at", "tenant_id"):
        raise ValueError("order_by is not a declared column: %r" % (order_by,))
    clauses = [_identifier("tenant_id") + " = " + _ph()]
    params: List[Any] = [str(tenant_id)]
    for name, value in (filters or {}).items():
        if name not in cols:
            raise ValueError("filter is not a declared column: %r" % (name,))
        clauses.append(_identifier(name) + " = " + _ph())
        params.append(value)
    sql = " ".join([
        "SELECT * FROM", _identifier(entity), "WHERE", " AND ".join(clauses),
        "ORDER BY", _identifier(order_by),
    ])
    with _WRITE_LOCK:
        conn = db.shared()
        rows = conn.execute(sql, params).fetchall()
    return [_row(row) for row in rows]


def update(entity: str, record_id: int, fields: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    cols = _columns(entity)
    changes = [(name, value) for name, value in (fields or {}).items() if name in cols]
    if not changes:
        return get(entity, record_id, tenant_id)
    assignments = ", ".join(_identifier(name) + " = " + _ph() for name, _ in changes)
    sql = " ".join([
        "UPDATE", _identifier(entity), "SET", assignments,
        "WHERE", _identifier("id"), "=", _ph(),
        "AND", _identifier("tenant_id"), "=", _ph(),
    ])
    params: List[Any] = [value for _, value in changes] + [record_id, str(tenant_id)]
    with _WRITE_LOCK:
        conn = db.shared()
        conn.execute(sql, params)
        conn.commit()
    return get(entity, record_id, tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    sql = " ".join([
        "DELETE FROM", _identifier(entity),
        "WHERE", _identifier("id"), "=", _ph(),
        "AND", _identifier("tenant_id"), "=", _ph(),
    ])
    with _WRITE_LOCK:
        conn = db.shared()
        cur = conn.execute(sql, [record_id, str(tenant_id)])
        conn.commit()
        return bool(getattr(cur, "rowcount", 0))


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def entities() -> Iterable[str]:
    return COLUMNS.keys()
