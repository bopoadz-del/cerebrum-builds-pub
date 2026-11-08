"""Durable work queue and idempotency ledger over the platform database."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa

from app import db

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_META = sa.MetaData()
_TABLES: Dict[str, sa.Table] = {}


def _table(name: str) -> sa.Table:
    global _TABLES
    engine = db.get_engine()
    key = "%s|%s" % (engine.url, name)
    if key not in _TABLES:
        _TABLES[key] = sa.Table(name, _META, autoload_with=engine)
    return _TABLES[key]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _item(row: Any) -> Dict[str, Any]:
    mapping = row._mapping
    try:
        payload = json.loads(mapping["payload"] or "{}")
    except (TypeError, ValueError):
        payload = {}
    result: Any = None
    if mapping["result"]:
        try:
            result = json.loads(mapping["result"])
        except (TypeError, ValueError):
            result = mapping["result"]
    return {
        "id": int(mapping["id"]),
        "tenant_id": mapping["tenant_id"],
        "capability_id": mapping["capability_id"],
        "payload": payload,
        "status": mapping["status"],
        "result": result,
        "created_at": mapping["created_at"],
        "updated_at": mapping["updated_at"],
    }


def enqueue(capability_id: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None, tenant_id: str = "") -> Dict[str, Any]:
    if not tenant_id:
        raise ValueError("tenant_id is required: the queue is tenant-scoped")
    if idempotency_key:
        remembered = recall(str(idempotency_key), tenant_id=tenant_id)
        if remembered:
            existing = get(int(remembered["record_id"]), tenant_id=tenant_id)
            if existing is not None:
                return existing
    table = _table("work_queue")
    stamp = _now()
    with db.get_engine().begin() as conn:
        result = conn.execute(
            sa.insert(table).values(
                tenant_id=str(tenant_id), capability_id=str(capability_id),
                payload=json.dumps(payload or {}, default=str), status=PENDING,
                result=None, created_at=stamp, updated_at=stamp,
            )
        )
        new_id = result.inserted_primary_key[0]
    if idempotency_key:
        remember(str(idempotency_key), "work_queue", int(new_id), tenant_id=tenant_id)
    item = get(int(new_id), tenant_id=tenant_id)
    if item is None:
        raise RuntimeError("enqueue did not persist")
    return item


def get(item_id: int, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    table = _table("work_queue")
    query = sa.select(table).where(table.c.id == int(item_id))
    if tenant_id:
        query = query.where(table.c.tenant_id == str(tenant_id))
    with db.get_engine().connect() as conn:
        row = conn.execute(query).first()
    return _item(row) if row is not None else None


def claim_pending(item_id: int, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    table = _table("work_queue")
    with db.get_engine().begin() as conn:
        update = sa.update(table).where(
            table.c.id == int(item_id), table.c.status == PENDING
        )
        if tenant_id:
            update = update.where(table.c.tenant_id == str(tenant_id))
        result = conn.execute(update.values(status=PROCESSING, updated_at=_now()))
        if not result.rowcount:
            return None
    return get(item_id, tenant_id=tenant_id)


def mark(item_id: int, status: str, result: Any = None, from_status: Optional[str] = None) -> Optional[Dict[str, Any]]:
    table = _table("work_queue")
    with db.get_engine().begin() as conn:
        update = sa.update(table).where(table.c.id == int(item_id))
        if from_status:
            update = update.where(table.c.status == from_status)
        changed = conn.execute(
            update.values(status=str(status), result=json.dumps(result, default=str), updated_at=_now())
        )
        if not changed.rowcount:
            return None
    return get(item_id)


def remember(key: str, entity: str, record_id: int, tenant_id: str = "") -> None:
    """Record an idempotency key for one tenant.

    Keys are unique per tenant (never globally): a key another tenant chose
    can neither recall that tenant's row nor block this one's insert.
    """
    from app import store

    tenant_id = str(tenant_id or store.tenant_of(entity, record_id) or "")
    table = _table("idempotency")
    with db.get_engine().begin() as conn:
        existing = conn.execute(
            sa.select(table).where(
                table.c.key == str(key), table.c.tenant_id == tenant_id
            )
        ).first()
        if existing is not None:
            return
        conn.execute(
            sa.insert(table).values(
                tenant_id=tenant_id, key=str(key), entity=str(entity),
                record_id=int(record_id), created_at=_now(),
            )
        )


def recall(key: str, tenant_id: str = "") -> Optional[Dict[str, Any]]:
    table = _table("idempotency")
    query = sa.select(table).where(table.c.key == str(key))
    if tenant_id:
        query = query.where(table.c.tenant_id == str(tenant_id))
    with db.get_engine().connect() as conn:
        row = conn.execute(query.order_by(table.c.id.desc()).limit(1)).first()
    if row is None:
        return None
    return {
        "entity": row._mapping["entity"],
        "record_id": int(row._mapping["record_id"]),
        "tenant_id": row._mapping["tenant_id"],
    }


def list_items(tenant_id: str = "", capability_id: Optional[str] = None) -> List[Dict[str, Any]]:
    table = _table("work_queue")
    query = sa.select(table)
    if tenant_id:
        query = query.where(table.c.tenant_id == str(tenant_id))
    if capability_id:
        query = query.where(table.c.capability_id == str(capability_id))
    with db.get_engine().connect() as conn:
        rows = conn.execute(query.order_by(table.c.id)).fetchall()
    return [_item(row) for row in rows]
