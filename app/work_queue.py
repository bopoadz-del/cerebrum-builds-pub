"""The platform work queue: enqueue a capability payload, claim it, run it,
record the outcome. Rows live in the same store and the same tenant scope as
every other record.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app import store

ENTITY = "work_queue"
IDEMPOTENCY_ENTITY = "idempotency"

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_TERMINAL = {PROCESSED, FAILED}


def _decode(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    out = dict(row)
    for key in ("payload", "result"):
        raw = out.get(key)
        if isinstance(raw, str) and raw:
            try:
                out[key] = json.loads(raw)
            except ValueError:
                pass
    return out


def _encode(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, sort_keys=True, default=str)


def recall(key: str, tenant_id: str = "local") -> Optional[Dict[str, Any]]:
    rows = store.query(IDEMPOTENCY_ENTITY, tenant_id=tenant_id, key=str(key))
    return rows[0] if rows else None


def remember(key: str, entity: str, record_id: int, tenant_id: str = "local") -> Dict[str, Any]:
    return store.save(
        IDEMPOTENCY_ENTITY,
        {"key": str(key), "entity": str(entity), "record_id": int(record_id)},
        tenant_id=tenant_id,
    )


def enqueue(
    capability_id: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    tenant_id: str = "local",
) -> Dict[str, Any]:
    row = store.save(
        ENTITY,
        {
            "capability_id": str(capability_id),
            "payload": _encode(payload),
            "status": PENDING,
            "idempotency_key": str(idempotency_key or ""),
            "result": "",
        },
        tenant_id=tenant_id,
    )
    return _decode(row) or {}


def get(item_id: int, tenant_id: str = "local") -> Optional[Dict[str, Any]]:
    return _decode(store.get(ENTITY, int(item_id), tenant_id=tenant_id))


def list_items(tenant_id: str = "local") -> List[Dict[str, Any]]:
    return [_decode(row) or {} for row in store.list_all(ENTITY, tenant_id=tenant_id)]


def claim_pending(item_id: int, tenant_id: str = "local") -> Optional[Dict[str, Any]]:
    """Atomically move one pending item to processing. None if it was not
    pending (already claimed, processed, or absent)."""
    current = get(item_id, tenant_id=tenant_id)
    if current is None or current.get("status") != PENDING:
        return None
    store.update(ENTITY, int(item_id), {"status": PROCESSING}, tenant_id=tenant_id)
    claimed = get(item_id, tenant_id=tenant_id)
    if claimed is None or claimed.get("status") != PROCESSING:
        return None
    return claimed


def mark(
    item_id: int,
    status: str,
    result: Any,
    from_status: str = PROCESSING,
    tenant_id: str = "local",
) -> Optional[Dict[str, Any]]:
    if status not in _TERMINAL:
        raise ValueError(f"a queue item is marked terminal, not {status!r}")
    current = get(item_id, tenant_id=tenant_id)
    if current is None or current.get("status") != from_status:
        return None
    store.update(
        ENTITY,
        int(item_id),
        {"status": status, "result": _encode(result)},
        tenant_id=tenant_id,
    )
    return get(item_id, tenant_id=tenant_id)
