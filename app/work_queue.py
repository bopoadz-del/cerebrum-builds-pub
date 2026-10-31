"""Persisted work queue and idempotency ledger.

A queued item is claimed in one conditional UPDATE, processed as its own
tenant, and marked processed/failed. A second claim of the same item fails
closed; an idempotency key replays the row it first created.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from sqlalchemy import select, update

from app import db as _db
from app import store

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _table():
    return store._table("work_queue")


def recall(key: str) -> Optional[Dict[str, Any]]:
    table = store._table("idempotency")
    with _db.engine().connect() as conn:
        row = conn.execute(select(table).where(table.c.key == str(key))).first()
    if row is None:
        return None
    return {"entity": row._mapping["entity"], "record_id": row._mapping["record_id"]}


def remember(key: str, entity: str, record_id: int, tenant_id: str = "") -> None:
    table = store._table("idempotency")
    with _db.engine().begin() as conn:
        existing = conn.execute(select(table).where(table.c.key == str(key))).first()
        if existing is not None:
            return
        conn.execute(
            table.insert().values(
                key=str(key),
                tenant_id=str(tenant_id or "platform"),
                entity=str(entity),
                record_id=int(record_id),
                created_at=_now(),
            )
        )


def enqueue(capability_id: str, payload: Dict[str, Any], idempotency_key: str = "",
            tenant_id: str = "") -> Dict[str, Any]:
    key = str(idempotency_key or "")
    if key:
        hit = recall(key)
        if hit is not None:
            existing = store.get(hit["entity"], int(hit["record_id"]), tenant_id=tenant_id)
            if existing is not None:
                return {**existing, "status": PROCESSED, "replayed": True}
    return store.save(
        "work_queue",
        {
            "capability_id": capability_id,
            "payload": dict(payload or {}),
            "status": PENDING,
            "idempotency_key": key or None,
        },
        tenant_id=tenant_id,
    )


def get(item_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    return store.get("work_queue", int(item_id), tenant_id=tenant_id)


def claim_pending(item_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    table = _table()
    now = _now()
    with _db.engine().begin() as conn:
        result = conn.execute(
            update(table)
            .where(
                table.c.id == int(item_id),
                table.c.tenant_id == tenant_id,
                table.c.status == PENDING,
            )
            .values(status=PROCESSING, updated_at=now)
        )
        claimed = bool(result.rowcount)
    if not claimed:
        return None
    return get(int(item_id), tenant_id)


def mark(item_id: int, status: str, result: Optional[Dict[str, Any]] = None,
         from_status: str = PROCESSING) -> Optional[Dict[str, Any]]:
    table = _table()
    with _db.engine().begin() as conn:
        row = conn.execute(select(table).where(table.c.id == int(item_id))).first()
        if row is None:
            return None
        tenant_id = row._mapping["tenant_id"]
        updated = conn.execute(
            update(table)
            .where(table.c.id == int(item_id), table.c.status == from_status)
            .values(
                status=status,
                result_json=json.dumps(result or {}, sort_keys=True, default=str),
                updated_at=_now(),
            )
        )
        if not updated.rowcount:
            return None
    return get(int(item_id), tenant_id)
