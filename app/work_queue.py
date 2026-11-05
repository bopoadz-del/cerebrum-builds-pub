"""Tenant-scoped work queue used by the kernel domain outcomes.

Items live in the ``work_queue`` table through app.store. Claiming is
serialized in process so two workers cannot claim the same pending item.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from app import store

ENTITY = "work_queue"
IDEMPOTENCY_ENTITY = "idempotency"

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

_LOCK = threading.RLock()


def _items(tenant_id: str) -> List[Dict[str, Any]]:
    return store.list_all(ENTITY, tenant_id)


def enqueue(
    capability_id: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    tenant_id: str = "local",
) -> Dict[str, Any]:
    with _LOCK:
        if idempotency_key:
            for item in _items(tenant_id):
                if item.get("idempotency_key") == idempotency_key:
                    return item
        record = {
            "reference": "queue-%d" % int(time.time() * 1000),
            "status": PENDING,
            "capability_id": str(capability_id),
            "payload": dict(payload or {}),
            "idempotency_key": idempotency_key or "",
            "attempts": 0,
        }
        return store.save(ENTITY, record, tenant_id)


def get(item_id: int, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if tenant_id is not None:
        return store.get(ENTITY, int(item_id), tenant_id)
    for tenant in _tenants():
        row = store.get(ENTITY, int(item_id), tenant)
        if row is not None:
            return row
    return None


def _tenants() -> List[str]:
    seen = set()
    tenants: List[str] = []
    for row in store.list_all(ENTITY, "local"):
        tenant = str(row.get("tenant_id") or "local")
        if tenant not in seen:
            seen.add(tenant)
            tenants.append(tenant)
    return tenants or ["local"]


def claim_pending(item_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        row = store.get(ENTITY, int(item_id), tenant_id)
        if row is None or row.get("status") != PENDING:
            return None
        return store.update(
            ENTITY,
            int(item_id),
            {"status": PROCESSING, "claimed_at": time.time()},
            tenant_id,
        )


def mark(
    item_id: int,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    from_status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _LOCK:
        row = get(int(item_id))
        if row is None:
            return None
        if from_status is not None and row.get("status") != from_status:
            return None
        return store.update(
            ENTITY,
            int(item_id),
            {
                "status": status,
                "result": dict(output or {}),
                "finished_at": time.time(),
            },
            row["tenant_id"],
        )


def recall(key: str) -> Optional[Dict[str, Any]]:
    for row in store.list_all(IDEMPOTENCY_ENTITY, "local"):
        if row.get("reference") == str(key):
            return {"entity": row.get("entity"), "record_id": row.get("record_id")}
    return None


def remember(key: str, entity: str, record_id: int) -> Dict[str, Any]:
    return store.save(
        IDEMPOTENCY_ENTITY,
        {"reference": str(key), "status": "open", "entity": entity, "record_id": int(record_id)},
        "local",
    )
