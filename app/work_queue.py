"""In-process work queue for the domain process contract.

A queued item is claimed exactly once and processed as the tenant that
enqueued it. The queue is deliberately small: it carries the payload, the
tenant and the terminal result, with a state machine that refuses to
process an item that is not pending.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_LOCK = threading.RLock()
_ITEMS: Dict[int, Dict[str, Any]] = {}
_IDEMPOTENCY: Dict[str, Dict[str, Any]] = {}
_NEXT_ID = [0]


def _copy(item: Dict[str, Any]) -> Dict[str, Any]:
    return dict(item)


def enqueue(capability_id: str, payload: Dict[str, Any], *,
            idempotency_key: Optional[str] = None,
            tenant_id: str = "") -> Dict[str, Any]:
    with _LOCK:
        if idempotency_key and idempotency_key in _IDEMPOTENCY:
            return _copy(_ITEMS[int(_IDEMPOTENCY[idempotency_key]["item_id"])])
        _NEXT_ID[0] += 1
        item = {
            "id": _NEXT_ID[0],
            "token": uuid.uuid4().hex,
            "capability_id": capability_id,
            "payload": dict(payload),
            "tenant_id": tenant_id,
            "status": PENDING,
            "result": None,
            "created_at": time.time(),
        }
        _ITEMS[item["id"]] = item
        if idempotency_key:
            _IDEMPOTENCY[idempotency_key] = {"item_id": item["id"]}
        return _copy(item)


def get(item_id: int, *, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None:
            return None
        if tenant_id is not None and item["tenant_id"] != tenant_id:
            return None
        return _copy(item)


def claim_pending(item_id: int, *, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None or item["status"] != PENDING:
            return None
        if tenant_id is not None and item["tenant_id"] != tenant_id:
            return None
        item["status"] = PROCESSING
        item["claimed_at"] = time.time()
        return _copy(item)


def mark(item_id: int, status: str, result: Any = None, *, from_status: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        item = _ITEMS.get(int(item_id))
        if item is None:
            return None
        if from_status is not None and item["status"] != from_status:
            return None
        item["status"] = status
        item["result"] = result
        item["finished_at"] = time.time()
        return _copy(item)


def remember(key: str, entity: str, record_id: int) -> None:
    with _LOCK:
        _IDEMPOTENCY[str(key)] = {"entity": entity, "record_id": int(record_id)}


def recall(key: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        hit = _IDEMPOTENCY.get(str(key))
        return dict(hit) if hit and "record_id" in hit else None


def reset() -> None:
    with _LOCK:
        _ITEMS.clear()
        _IDEMPOTENCY.clear()
        _NEXT_ID[0] = 0
