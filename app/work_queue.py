"""Durable work queue behind the product.process kernel action.

Rows live in the same database app.db selects, so a pending item survives a
restart instead of disappearing with the process. Statements are literal and
every value is a bound parameter.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app import db as _db

PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"

INSERT_QUEUE = (
    "INSERT INTO work_queue (capability_id, tenant_id, payload_json, status,"
    " idempotency_key, created_at, updated_at)"
    " VALUES (:capability_id, :tenant_id, :payload_json, :status,"
    " :idempotency_key, :created_at, :updated_at)"
)
INSERT_QUEUE_RETURNING = INSERT_QUEUE + " RETURNING id"
SELECT_QUEUE = "SELECT * FROM work_queue WHERE id = :id AND tenant_id = :tenant_id"
LIST_QUEUE = (
    "SELECT * FROM work_queue WHERE tenant_id = :tenant_id ORDER BY id LIMIT :limit"
)
SELECT_QUEUE_TENANT = "SELECT tenant_id FROM work_queue WHERE id = :id"
CLAIM_QUEUE = (
    "UPDATE work_queue SET status = :status, updated_at = :updated_at"
    " WHERE id = :id AND tenant_id = :tenant_id AND status = :expected"
)
MARK_QUEUE = (
    "UPDATE work_queue SET status = :status, result_json = :result_json, updated_at = :updated_at"
    " WHERE id = :id AND tenant_id = :tenant_id"
)
MARK_QUEUE_FROM = MARK_QUEUE + " AND status = :from_status"
SELECT_IDEMPOTENCY = (
    "SELECT entity, record_id, tenant_id FROM idempotency WHERE idempotency_key = :idempotency_key"
)
INSERT_IDEMPOTENCY = (
    "INSERT INTO idempotency (idempotency_key, tenant_id, entity, record_id, created_at)"
    " VALUES (:idempotency_key, :tenant_id, :entity, :record_id, :created_at)"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row) -> Optional[dict]:
    if row is None:
        return None
    data = dict(row) if not isinstance(row, dict) else dict(row)
    payload = data.get("payload_json")
    result = data.get("result_json")
    return {
        "id": data.get("id"),
        "capability_id": data.get("capability_id"),
        "tenant_id": data.get("tenant_id"),
        "status": data.get("status"),
        "idempotency_key": data.get("idempotency_key"),
        "payload": json.loads(payload) if isinstance(payload, str) and payload else {},
        "result": json.loads(result) if isinstance(result, str) and result else None,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def enqueue(capability_id: str, payload: dict, idempotency_key: Optional[str] = None, tenant_id: Optional[str] = None) -> dict:
    if not tenant_id:
        raise ValueError("tenant_id is required")
    now = _now()
    params = {
        "capability_id": capability_id,
        "tenant_id": tenant_id,
        "payload_json": json.dumps(payload or {}, ensure_ascii=True, default=str),
        "status": PENDING,
        "idempotency_key": idempotency_key,
        "created_at": now,
        "updated_at": now,
    }
    connection = _db.connect()
    try:
        if _db.backend_name() == "postgres":
            fetched = connection.execute(INSERT_QUEUE_RETURNING, params).fetchone()
            item_id = fetched[0] if fetched else None
        else:
            item_id = connection.execute(INSERT_QUEUE, params).lastrowid
        connection.commit()
    finally:
        connection.close()
    return get(item_id, tenant_id=tenant_id) or {}


def get(item_id: int, tenant_id: str) -> Optional[dict]:
    connection = _db.connect()
    try:
        row = connection.execute(SELECT_QUEUE, {"id": item_id, "tenant_id": tenant_id}).fetchone()
    finally:
        connection.close()
    return _row(row)


def claim_pending(item_id: int, tenant_id: str) -> Optional[dict]:
    params = {
        "status": PROCESSING,
        "updated_at": _now(),
        "id": item_id,
        "tenant_id": tenant_id,
        "expected": PENDING,
    }
    connection = _db.connect()
    try:
        cursor = connection.execute(CLAIM_QUEUE, params)
        connection.commit()
        claimed = cursor.rowcount
    finally:
        connection.close()
    return get(item_id, tenant_id=tenant_id) if claimed else None


def mark(item_id: int, status: str, result: Any = None, from_status: Optional[str] = None) -> Optional[dict]:
    connection = _db.connect()
    try:
        row = connection.execute(SELECT_QUEUE_TENANT, {"id": item_id}).fetchone()
        if row is None:
            return None
        tenant_id = row[0] if not isinstance(row, dict) else row["tenant_id"]
        params = {
            "status": status,
            "result_json": json.dumps(result, ensure_ascii=True, default=str),
            "updated_at": _now(),
            "id": item_id,
            "tenant_id": tenant_id,
        }
        if from_status:
            params["from_status"] = from_status
            connection.execute(MARK_QUEUE_FROM, params)
        else:
            connection.execute(MARK_QUEUE, params)
        connection.commit()
    finally:
        connection.close()
    return get(item_id, tenant_id=tenant_id)


def list_items(tenant_id: str, limit: int = 100) -> list:
    """The caller's own queue rows, oldest first. Never another tenant's."""
    if not tenant_id:
        raise ValueError("tenant_id is required")
    connection = _db.connect()
    try:
        rows = connection.execute(
            LIST_QUEUE, {"tenant_id": tenant_id, "limit": int(limit)}
        ).fetchall()
    finally:
        connection.close()
    return [item for item in (_row(row) for row in rows) if item is not None]


def recall(idempotency_key: str) -> Optional[dict]:
    connection = _db.connect()
    try:
        row = connection.execute(SELECT_IDEMPOTENCY, {"idempotency_key": idempotency_key}).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    data = dict(row) if not isinstance(row, dict) else row
    return {"entity": data["entity"], "record_id": data["record_id"], "tenant_id": data.get("tenant_id")}


def remember(idempotency_key: str, entity: str, record_id: int, tenant_id: str = "local") -> None:
    params = {
        "idempotency_key": idempotency_key,
        "tenant_id": tenant_id,
        "entity": entity,
        "record_id": record_id,
        "created_at": _now(),
    }
    connection = _db.connect()
    try:
        connection.execute(INSERT_IDEMPOTENCY, params)
        connection.commit()
    finally:
        connection.close()
