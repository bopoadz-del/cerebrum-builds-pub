"""The platform's queue: one pending item per request, claimed once.

The S12 driver enqueues a domain record, claims it, executes the capability
and marks the item processed or failed.  Status changes are conditional on
the status the caller saw (``from_status``), so two workers cannot both claim
the same item.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, insert, select, update

from app import db as _db

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_metadata = MetaData()

_QUEUE = Table(
    "work_queue",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("capability_id", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", Text, nullable=False),
    Column("result", Text, nullable=True),
    Column("created_at", String(40), nullable=False),
)

_IDEMPOTENCY = Table(
    "idempotency",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("idempotency_key", String(200), nullable=False, index=True),
    Column("entity", String(128), nullable=False),
    Column("record_id", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    payload = out.get("payload")
    if isinstance(payload, str):
        try:
            out["payload"] = json.loads(payload)
        except ValueError:
            out["payload"] = {}
    result = out.get("result")
    if isinstance(result, str) and result:
        try:
            out["result"] = json.loads(result)
        except ValueError:
            pass
    return out


def enqueue(
    capability_id: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    tenant_id: str = "",
) -> Dict[str, Any]:
    if not tenant_id:
        raise ValueError("tenant_id is required: a queue item is never tenantless")
    if idempotency_key:
        existing = recall(str(idempotency_key), tenant_id=tenant_id)
        if existing:
            item = get(int(existing["record_id"]), tenant_id=tenant_id)
            if item is not None:
                return item
    values = {
        "tenant_id": str(tenant_id),
        "capability_id": str(capability_id),
        "status": PENDING,
        "payload": json.dumps(dict(payload or {}), sort_keys=True, default=str),
        "result": None,
        "created_at": _now(),
    }
    with _db.engine().begin() as conn:
        result = conn.execute(insert(_QUEUE).values(**values))
        item_id = getattr(result, "lastrowid", None)
    item = get(int(item_id), tenant_id=tenant_id) if item_id is not None else None
    return item or {"id": item_id, "status": PENDING, "payload": dict(payload or {})}


def get(item_id: Any, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    try:
        key = int(item_id)
    except (TypeError, ValueError):
        return None
    statement = select(_QUEUE).where(_QUEUE.c.id == key)
    if tenant_id:
        statement = statement.where(_QUEUE.c.tenant_id == str(tenant_id))
    with _db.engine().connect() as conn:
        row = conn.execute(statement).mappings().first()
    return _row(dict(row)) if row is not None else None


def list_items(status: Optional[str] = None, tenant_id: str = "") -> List[Dict[str, Any]]:
    statement = select(_QUEUE).order_by(_QUEUE.c.id)
    if status:
        statement = statement.where(_QUEUE.c.status == str(status))
    if tenant_id:
        statement = statement.where(_QUEUE.c.tenant_id == str(tenant_id))
    with _db.engine().connect() as conn:
        rows = conn.execute(statement).mappings().all()
    return [_row(dict(row)) for row in rows]


def claim_pending(item_id: Any, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    """Move one pending item to processing; None when it is not pending."""
    try:
        key = int(item_id)
    except (TypeError, ValueError):
        return None
    statement = (
        update(_QUEUE)
        .where(_QUEUE.c.id == key, _QUEUE.c.status == PENDING)
        .values(status=PROCESSING)
    )
    if tenant_id:
        statement = statement.where(_QUEUE.c.tenant_id == str(tenant_id))
    with _db.engine().begin() as conn:
        result = conn.execute(statement)
        if not result.rowcount:
            return None
    return get(key, tenant_id=tenant_id)


def mark(
    item_id: Any,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    from_status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        key = int(item_id)
    except (TypeError, ValueError):
        return None
    statement = update(_QUEUE).where(_QUEUE.c.id == key).values(status=str(status))
    if from_status:
        statement = statement.where(_QUEUE.c.status == str(from_status))
    if result is not None:
        statement = statement.values(result=json.dumps(result, sort_keys=True, default=str))
    with _db.engine().begin() as conn:
        changed = conn.execute(statement)
        if not changed.rowcount:
            return None
    return get(key)


def recall(idempotency_key: str, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    key = str(idempotency_key or "")
    if not key:
        return None
    statement = select(_IDEMPOTENCY).where(_IDEMPOTENCY.c.idempotency_key == key)
    if tenant_id:
        statement = statement.where(_IDEMPOTENCY.c.tenant_id == str(tenant_id))
    with _db.engine().connect() as conn:
        row = conn.execute(statement.order_by(_IDEMPOTENCY.c.id)).mappings().first()
    return dict(row) if row is not None else None


def remember(idempotency_key: str, entity: str, record_id: int, tenant_id: str = "") -> Dict[str, Any]:
    key = str(idempotency_key or "")
    if not key:
        raise ValueError("idempotency_key is required")
    values = {
        "tenant_id": str(tenant_id or "local"),
        "idempotency_key": key,
        "entity": str(entity),
        "record_id": int(record_id),
        "created_at": _now(),
    }
    with _db.engine().begin() as conn:
        existing = conn.execute(
            select(_IDEMPOTENCY).where(
                _IDEMPOTENCY.c.idempotency_key == key,
                _IDEMPOTENCY.c.tenant_id == values["tenant_id"],
            )
        ).mappings().first()
        if existing is not None:
            return dict(existing)
        conn.execute(insert(_IDEMPOTENCY).values(**values))
    return dict(values, id=None)


def new_key(prefix: str = "") -> str:
    return "%s%s" % (prefix, uuid.uuid4().hex)
