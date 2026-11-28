"""In-process work queue used by the S12 domain outcomes.

The queue is deliberately small and deterministic: enqueue stores a pending
item for one tenant, claim_pending moves it to processing, mark records the
outcome, and an idempotency key recalls the item a prior enqueue produced.
An item is never visible to another tenant.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_LOCK = threading.RLock()
_ITEMS: Dict[int, Dict[str, Any]] = {}
_KEYS: Dict[str, Dict[str, Any]] = {}
_QUEUE_KEYS: Dict[str, Dict[str, Any]] = {}
_NEXT = [1]


def _copy(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return dict(item) if item is not None else None


def enqueue(
    capability_id: str,
    payload: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        key = str(idempotency_key) if idempotency_key else ""
        if key:
            prior = _QUEUE_KEYS.get(key)
            if prior is not None and prior.get("tenant_id") == str(tenant_id or "") \
                    and prior.get("item_id") is not None:
                item = _ITEMS.get(prior["item_id"])
                if item is not None:
                    return dict(item)
        item_id = _NEXT[0]
        _NEXT[0] += 1
        item = {
            "id": item_id,
            "capability_id": str(capability_id or ""),
            "tenant_id": str(tenant_id or ""),
            "idempotency_key": key or None,
            "payload": dict(payload or {}),
            "status": PENDING,
            "result": None,
        }
        _ITEMS[item_id] = item
        if key:
            _QUEUE_KEYS[key] = {"item_id": item_id, "tenant_id": item["tenant_id"]}
        return dict(item)


def get(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None:
            return None
        if tenant_id is not None and str(item.get("tenant_id") or "") != str(tenant_id):
            return None
        return dict(item)


def claim_pending(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None or item.get("status") != PENDING:
            return None
        if tenant_id is not None and str(item.get("tenant_id") or "") != str(tenant_id):
            return None
        item["status"] = PROCESSING
        return dict(item)


def mark(
    item_id: int,
    status: str,
    result: Any = None,
    tenant_id: Optional[str] = None,
    from_status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None:
            return None
        if tenant_id is not None and str(item.get("tenant_id") or "") != str(tenant_id):
            return None
        if from_status is not None and item.get("status") != from_status:
            return None
        item["status"] = str(status)
        item["result"] = result
        return dict(item)


def process(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    claimed = claim_pending(item_id, tenant_id=tenant_id)
    if claimed is None:
        return get(item_id, tenant_id=tenant_id)
    return mark(
        int(item_id),
        PROCESSED,
        {"ok": True, "item_id": int(item_id), "processed": True},
        tenant_id=tenant_id,
        from_status=PROCESSING,
    )


def remember(key: str, entity: str, record_id: int) -> None:
    with _LOCK:
        _KEYS[str(key)] = {"entity": entity, "record_id": record_id}


def recall(key: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        hit = _KEYS.get(str(key))
        return dict(hit) if hit else None


def reset() -> None:
    with _LOCK:
        _ITEMS.clear()
        _KEYS.clear()
        _QUEUE_KEYS.clear()
        _NEXT[0] = 1
