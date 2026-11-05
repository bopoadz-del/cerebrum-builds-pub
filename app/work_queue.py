"""The kernel's work queue: enqueue, claim, process, mark.

S12's queue outcome is "the pending item is processed, not a no-op", so a
claim moves the row to ``processing`` under a conditional update (two workers
cannot both win it) and ``mark`` records the outcome the kernel returned. A
queue item carries the tenant that enqueued it; processing runs as that
tenant, never as whoever happens to poll.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete as _delete, select as _select, update as _update

from app import db, store

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

ENTITY = "work_queue"
IDEMPOTENCY = "idempotency"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encoded(value: Any) -> str:
    return json.dumps(value, default=str)


def _decode(value: Any) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _row(row: Any) -> Dict[str, Any]:
    mapping = row._mapping
    return {
        "id": mapping["id"],
        "tenant_id": mapping["tenant_id"],
        "capability_id": _decode(mapping["capability_id"]),
        "payload": _decode(mapping["payload"]),
        "status": _decode(mapping["status"]),
        "attempts": mapping["attempts"],
        "result": _decode(mapping["result"]),
        "idempotency_key": _decode(mapping["idempotency_key"]),
        "created_at": mapping["created_at"],
    }


def _select_by_id(item_id: Any, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    table = store._table(ENTITY)
    statement = _select(table).where(table.c.id == int(item_id))
    if tenant_id is not None:
        statement = statement.where(table.c.tenant_id == str(tenant_id))
    with db.engine().connect() as conn:
        row = conn.execute(statement).first()
    return _row(row) if row is not None else None


def recall(key: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The idempotency ledger row a previous request with this key produced."""
    table = store._table(IDEMPOTENCY)
    statement = _select(table).where(table.c.idempotency_key == _encoded(str(key)))
    if tenant_id is not None:
        statement = statement.where(table.c.tenant_id == str(tenant_id))
    with db.engine().connect() as conn:
        row = conn.execute(statement.order_by(table.c.id)).first()
    if row is None:
        return None
    mapping = row._mapping
    return {
        "id": mapping["id"],
        "tenant_id": mapping["tenant_id"],
        "idempotency_key": _decode(mapping["idempotency_key"]),
        "entity": _decode(mapping["entity"]),
        "record_id": mapping["record_id"],
    }


def tenant_of_record(entity: str, record_id: Any) -> Optional[str]:
    """The tenant that owns a stored row (the ledger inherits its tenant)."""
    table = store._table(entity)
    with db.engine().connect() as conn:
        row = conn.execute(
            _select(table.c.tenant_id).where(table.c.id == int(record_id))
        ).first()
    return str(row[0]) if row is not None else None


def remember(key: str, entity: str, record_id: int, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    tenant = tenant_id or tenant_of_record(entity, record_id)
    if not tenant:
        raise ValueError("the idempotency ledger needs the tenant of the record it points to")
    return store.save(
        IDEMPOTENCY,
        {"idempotency_key": str(key), "entity": str(entity), "record_id": int(record_id)},
        tenant_id=tenant,
    )


def forget(key: str, tenant_id: Optional[str] = None) -> None:
    table = store._table(IDEMPOTENCY)
    statement = _delete(table).where(table.c.idempotency_key == _encoded(str(key)))
    if tenant_id is not None:
        statement = statement.where(table.c.tenant_id == str(tenant_id))
    with db.engine().begin() as conn:
        conn.execute(statement)


def enqueue(
    capability_id: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    stored = store.save(
        ENTITY,
        {
            "capability_id": capability_id,
            "payload": payload,
            "status": PENDING,
            "attempts": 0,
            "result": None,
            "idempotency_key": idempotency_key,
        },
        tenant_id=tenant_id,
    )
    return _select_by_id(stored["id"], tenant_id) or stored


def get(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return _select_by_id(item_id, tenant_id)


def list_items(tenant_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    table = store._table(ENTITY)
    statement = _select(table).where(table.c.tenant_id == str(tenant_id or ""))
    if status:
        statement = statement.where(table.c.status == _encoded(status))
    with db.engine().connect() as conn:
        rows = conn.execute(statement.order_by(table.c.id)).fetchall()
    return [_row(row) for row in rows]


def claim_pending(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Move a pending item to processing. None when it was not pending."""
    table = store._table(ENTITY)
    statement = (
        _update(table)
        .where(table.c.id == int(item_id))
        .where(table.c.tenant_id == str(tenant_id or ""))
        .where(table.c.status == _encoded(PENDING))
        .values(status=_encoded(PROCESSING), updated_at=_now())
    )
    with db.engine().begin() as conn:
        result = conn.execute(statement)
        won = bool(result.rowcount)
    return _select_by_id(item_id, tenant_id) if won else None


def mark(
    item_id: int,
    status: str,
    result: Any = None,
    from_status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    current = _select_by_id(item_id)
    if current is None:
        return None
    table = store._table(ENTITY)
    statement = _update(table).where(table.c.id == int(item_id))
    if from_status:
        statement = statement.where(table.c.status == _encoded(from_status))
    with db.engine().begin() as conn:
        conn.execute(
            statement.values(
                status=_encoded(status),
                result=_encoded(result),
                updated_at=_now(),
            )
        )
    return _select_by_id(item_id, current.get("tenant_id"))
