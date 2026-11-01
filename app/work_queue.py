"""Persisted work queue processed through execute_action.

Enqueue writes a pending row. Process runs the capability through the
vendored kernel and records processed|failed plus the ActionResult.
A handler that returns ok without changing status is a hollow queue (F5).

Statements are SQLAlchemy Core over the declared queue and idempotency
tables, compiled for whichever backend app.db is on (SQLite by default,
Postgres when DATABASE_URL is set). No SQL text is assembled from names.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite as _sqlite_dialect

from app import db as _db

TABLE = 'work_queue'
IDEMPOTENCY = 'idempotency'
PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_QUEUE = sa.table(
    TABLE,
    sa.column("id"),
    sa.column("capability_id"),
    sa.column("tenant_id"),
    sa.column("payload"),
    sa.column("status"),
    sa.column("result"),
    sa.column("idempotency_key"),
)
_KEYS = sa.table(IDEMPOTENCY, sa.column("key"), sa.column("entity"), sa.column("record_id"))
_SQLITE = _sqlite_dialect.dialect(paramstyle="qmark")


def _execute(conn: Any, statement: Any) -> Any:
    """Run one Core statement on either backend's connection."""
    if _db.is_postgres():
        return conn.execute(statement)
    compiled = statement.compile(dialect=_SQLITE)
    params = [compiled.params[name] for name in (compiled.positiontup or ())]
    return conn.execute(str(compiled), params)


def enqueue(
    capability_id: str,
    payload: Dict[str, Any],
    *,
    idempotency_key: str | None = None,
    tenant_id: str,
) -> Dict[str, Any]:
    statement = sa.insert(_QUEUE).values(
        capability_id=capability_id,
        tenant_id=tenant_id,
        payload=json.dumps(payload, sort_keys=True),
        status=PENDING,
        result=None,
        idempotency_key=idempotency_key,
    )
    conn = _db.connect()
    try:
        if _db.is_postgres():
            item_id = int(_execute(conn, statement.returning(_QUEUE.c.id)).scalar_one())
        else:
            item_id = int(_execute(conn, statement).lastrowid)
        conn.commit()
    finally:
        conn.close()
    item = get(item_id)
    if item is None:
        raise RuntimeError("work_queue enqueue did not persist")
    return item


def _as_item_id(item_id: Any) -> int:
    """Queue ids are integers. JSON / sqlite / FastAPI may hand us a str."""
    return int(item_id)


def get(item_id: int, *, tenant_id: str | None = None) -> Dict[str, Any] | None:
    """One queue item. With ``tenant_id``, only that tenant's: another
    tenant's item reads as absent -- a 404, never someone else's work."""
    item_id = _as_item_id(item_id)
    statement = sa.select(_QUEUE).where(_QUEUE.c.id == item_id)
    if tenant_id is not None:
        statement = statement.where(_QUEUE.c.tenant_id == tenant_id)
    conn = _db.connect()
    try:
        row = _execute(conn, statement).fetchone()
        return _row(row) if row else None
    finally:
        conn.close()


def list_all(*, tenant_id: str) -> List[Dict[str, Any]]:
    """The caller's queue. Required, never defaulted: an unscoped list
    returned every tenant's items to any authenticated caller."""
    statement = (
        sa.select(_QUEUE).where(_QUEUE.c.tenant_id == tenant_id).order_by(_QUEUE.c.id)
    )
    conn = _db.connect()
    try:
        return [_row(r) for r in _execute(conn, statement).fetchall()]
    finally:
        conn.close()


def claim_pending(item_id: int, *, tenant_id: str) -> Dict[str, Any] | None:
    """Claim a pending item the caller's tenant owns. Another tenant's id
    claims nothing -- it used to claim anything, and processing then ran
    that item as its owner on a stranger's request."""
    item_id = _as_item_id(item_id)
    statement = (
        sa.update(_QUEUE)
        .where(
            _QUEUE.c.id == item_id,
            _QUEUE.c.status == PENDING,
            _QUEUE.c.tenant_id == tenant_id,
        )
        .values(status=PROCESSING)
    )
    conn = _db.connect()
    try:
        changed = _execute(conn, statement).rowcount
        conn.commit()
        if changed == 0:
            return None
    finally:
        conn.close()
    return get(item_id, tenant_id=tenant_id)


def mark(
    item_id: int,
    status: str,
    result: Dict[str, Any] | None,
    *,
    from_status: str | None = None,
) -> Dict[str, Any] | None:
    item_id = _as_item_id(item_id)
    statement = (
        sa.update(_QUEUE)
        .where(_QUEUE.c.id == item_id)
        .values(
            status=status,
            result=json.dumps(result, sort_keys=True) if result is not None else None,
        )
    )
    if from_status is not None:
        statement = statement.where(_QUEUE.c.status == from_status)
    conn = _db.connect()
    try:
        changed = _execute(conn, statement).rowcount
        conn.commit()
        if changed == 0:
            return None
    finally:
        conn.close()
    return get(item_id)


def recall(key: str) -> Dict[str, Any] | None:
    statement = sa.select(_KEYS).where(_KEYS.c.key == key)
    conn = _db.connect()
    try:
        row = _execute(conn, statement).fetchone()
        return _as_dict(row) if row else None
    finally:
        conn.close()


def remember(key: str, entity: str, record_id: int) -> None:
    """Record (or replace) what an idempotency key produced, atomically."""
    conn = _db.connect()
    try:
        _execute(conn, sa.delete(_KEYS).where(_KEYS.c.key == key))
        _execute(
            conn,
            sa.insert(_KEYS).values(key=key, entity=entity, record_id=record_id),
        )
        conn.commit()
    finally:
        conn.close()


def _as_dict(row: Any) -> Dict[str, Any]:
    mapping = getattr(row, "_mapping", None)
    return dict(mapping) if mapping is not None else dict(row)


def _row(row: Any) -> Dict[str, Any]:
    item = _as_dict(row)
    if item.get("id") is not None:
        try:
            item["id"] = int(item["id"])
        except (TypeError, ValueError):
            pass
    raw_payload = item.get("payload")
    if isinstance(raw_payload, str):
        try:
            item["payload"] = json.loads(raw_payload)
        except json.JSONDecodeError:
            pass
    raw_result = item.get("result")
    if isinstance(raw_result, str) and raw_result:
        try:
            item["result"] = json.loads(raw_result)
        except json.JSONDecodeError:
            pass
    return item
