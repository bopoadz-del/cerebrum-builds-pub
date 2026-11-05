"""Tenant-scoped persistence over the database app.db selects.

Schema belongs to Alembic. ``connect()`` never creates a table. Every entity is
the capability id (the stem of app/actions/<capability>.py); the route saves the
request record under the caller's tenant and reads it back through here.

Statements are literal constants per entity -- identifiers come from the
declared table map, never from a caller -- and every value is a bound parameter.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import db as _db

STORAGE_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = _db.BUSY_TIMEOUT_MS
FASTAPI_SYNC_THREADPOOL = int(os.environ.get("FASTAPI_SYNC_THREADPOOL", "40"))

BASE_COLUMNS = ["id", "tenant_id", "reference", "status", "payload_json", "created_at", "updated_at"]

COLUMNS = {
    "progress_claim_administration": list(BASE_COLUMNS),
    "delay_damages_tracking": list(BASE_COLUMNS),
    "qa_itp_records": list(BASE_COLUMNS),
    "document_register": list(BASE_COLUMNS),
}

_COLUMN_LIST = "id, tenant_id, reference, status, payload_json, created_at, updated_at"

INSERT_SQL = {
    entity: (
        "INSERT INTO " + entity
        + " (tenant_id, reference, status, payload_json, created_at, updated_at)"
        " VALUES (:tenant_id, :reference, :status, :payload_json, :created_at, :updated_at)"
    )
    for entity in COLUMNS
}

INSERT_SQL_RETURNING = {
    entity: INSERT_SQL[entity] + " RETURNING id"
    for entity in COLUMNS
}

SELECT_SQL = {
    entity: (
        "SELECT " + _COLUMN_LIST + " FROM " + entity
        + " WHERE id = :id AND tenant_id = :tenant_id"
    )
    for entity in COLUMNS
}

LIST_SQL = {
    entity: (
        "SELECT " + _COLUMN_LIST + " FROM " + entity
        + " WHERE tenant_id = :tenant_id ORDER BY id LIMIT :limit"
    )
    for entity in COLUMNS
}

UPDATE_SQL = {
    entity: (
        "UPDATE " + entity
        + " SET reference = :reference, status = :status, payload_json = :payload_json,"
        " updated_at = :updated_at WHERE id = :id AND tenant_id = :tenant_id"
    )
    for entity in COLUMNS
}

DELETE_SQL = {
    entity: (
        "DELETE FROM " + entity + " WHERE id = :id AND tenant_id = :tenant_id"
    )
    for entity in COLUMNS
}


def db_path() -> Path:
    return Path(_db.sqlite_path())


def connect():
    return _db.connect()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row) -> dict:
    data = row if isinstance(row, dict) else dict(row)
    payload = data.get("payload_json")
    if isinstance(payload, str):
        try:
            record = json.loads(payload)
        except ValueError:
            record = {}
    elif isinstance(payload, dict):
        record = dict(payload)
    else:
        record = {}
    if not isinstance(record, dict):
        record = {}
    record["id"] = data.get("id")
    record.setdefault("reference", data.get("reference"))
    record.setdefault("status", data.get("status"))
    record["tenant_id"] = data.get("tenant_id")
    if data.get("created_at") is not None:
        record["created_at"] = data.get("created_at")
    if data.get("updated_at") is not None:
        record["updated_at"] = data.get("updated_at")
    return record


def _require_entity(entity: str) -> None:
    if entity not in COLUMNS:
        raise KeyError("unknown entity: " + str(entity))
    if not entity or not str(entity).replace("_", "").isalnum():
        raise ValueError("entity must be a capability id")


def save(entity: str, record: dict, tenant_id: str) -> dict:
    _require_entity(entity)
    if not tenant_id:
        raise ValueError("tenant_id is required")
    stored = dict(record or {})
    stored.pop("tenant_id", None)
    stored.pop("created_at", None)
    stored.pop("updated_at", None)
    now = _now()
    params = {
        "tenant_id": tenant_id,
        "reference": str(stored.get("reference") or ""),
        "status": str(stored.get("status") or ""),
        "payload_json": json.dumps(stored, ensure_ascii=True, default=str),
        "created_at": now,
        "updated_at": now,
    }
    connection = connect()
    try:
        if _db.backend_name() == "postgres":
            row = connection.execute(INSERT_SQL_RETURNING[entity], params).fetchone()
            record_id = row[0] if row is not None else None
        else:
            cursor = connection.execute(INSERT_SQL[entity], params)
            record_id = cursor.lastrowid
        connection.commit()
    finally:
        connection.close()
    result = dict(stored)
    result["id"] = record_id
    result["tenant_id"] = tenant_id
    result["created_at"] = now
    result["updated_at"] = now
    return result


def get(entity: str, record_id: Any, tenant_id: str) -> Optional[dict]:
    _require_entity(entity)
    if not tenant_id:
        raise ValueError("tenant_id is required")
    connection = connect()
    try:
        row = connection.execute(SELECT_SQL[entity], {"id": record_id, "tenant_id": tenant_id}).fetchone()
    finally:
        connection.close()
    return _row_to_record(row) if row is not None else None


def list_all(entity: str, tenant_id: str, limit: int = 1000) -> list:
    _require_entity(entity)
    if not tenant_id:
        raise ValueError("tenant_id is required")
    connection = connect()
    try:
        rows = connection.execute(LIST_SQL[entity], {"tenant_id": tenant_id, "limit": int(limit)}).fetchall()
    finally:
        connection.close()
    return [_row_to_record(row) for row in rows]


def query(entity: str, tenant_id: str, filters: Optional[dict] = None, q: Optional[str] = None, limit: int = 100) -> list:
    rows = list_all(entity, tenant_id, limit=1000)
    out = []
    needle = str(q or "").strip().lower()
    for row in rows:
        if filters and any(str(row.get(key)) != str(value) for key, value in filters.items()):
            continue
        if needle and needle not in json.dumps(row, sort_keys=True, default=str).lower():
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def update(entity: str, record_id: Any, record: dict, tenant_id: str) -> Optional[dict]:
    current = get(entity, record_id, tenant_id)
    if current is None:
        return None
    merged = dict(current)
    merged.update({k: v for k, v in (record or {}).items() if k not in ("id", "tenant_id")})
    payload = dict(merged)
    payload.pop("id", None)
    payload.pop("tenant_id", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    params = {
        "reference": str(merged.get("reference") or ""),
        "status": str(merged.get("status") or ""),
        "payload_json": json.dumps(payload, ensure_ascii=True, default=str),
        "updated_at": _now(),
        "id": record_id,
        "tenant_id": tenant_id,
    }
    connection = connect()
    try:
        connection.execute(UPDATE_SQL[entity], params)
        connection.commit()
    finally:
        connection.close()
    return get(entity, record_id, tenant_id)


def delete(entity: str, record_id: Any, tenant_id: str) -> bool:
    _require_entity(entity)
    connection = connect()
    try:
        cursor = connection.execute(DELETE_SQL[entity], {"id": record_id, "tenant_id": tenant_id})
        connection.commit()
        deleted = cursor.rowcount
    finally:
        connection.close()
    return bool(deleted)
