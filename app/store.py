"""Tenant-scoped persistence over the database app.db selects.

The schema lives in alembic. ``connect()`` never creates a table. Records
are stored as JSON in a declared envelope column per entity, with the
searchable envelope fields promoted to columns (tenant_id, reference,
status, timestamps).
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, MetaData, String, Table, Text
from sqlalchemy import delete as sa_delete
from sqlalchemy import insert as sa_insert
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app import db as _db

STORAGE_PATH_ENV = "STORAGE_PATH"
SQLITE_BUSY_TIMEOUT_MS = _db.SQLITE_BUSY_TIMEOUT_MS
FASTAPI_SYNC_THREADPOOL = 8

ENTITIES: tuple[str, ...] = (
    "document_grounded_qa",
    "supplier_cost_and_parts_pricing",
    "cost_price_movement_alerts",
    "document_revision_nudges",
    "document_ingestion_from_m365_and_upload",
    "manager_dashboard",
    "manager_only_access",
    "sap_odata_connector",
    "rag_document",
    "work_queue",
    "idempotency",
    "lifecycle_audit",
)

COLUMNS: Dict[str, List[str]] = {
    entity: [
        "id",
        "tenant_id",
        "reference",
        "status",
        "payload_json",
        "created_at",
        "updated_at",
    ]
    for entity in ENTITIES
}
COLUMNS["work_queue"] = [
    "id",
    "tenant_id",
    "capability_id",
    "payload_json",
    "status",
    "idempotency_key",
    "result_json",
    "created_at",
    "updated_at",
]
COLUMNS["idempotency"] = ["key", "tenant_id", "entity", "record_id", "created_at"]
COLUMNS["lifecycle_audit"] = ["id", "tenant_id", "entity", "entity_id", "action", "created_at"]

_METADATA = MetaData()


def _table(entity: str) -> Table:
    if entity not in COLUMNS:
        raise KeyError(f"unknown entity: {entity}")
    if entity in _METADATA.tables:
        return _METADATA.tables[entity]
    if entity == "work_queue":
        return Table(
            entity,
            _METADATA,
            Column("id", Integer, primary_key=True),
            Column("tenant_id", String, nullable=False, index=True),
            Column("capability_id", String, nullable=False),
            Column("payload_json", Text, nullable=False),
            Column("status", String, nullable=False),
            Column("idempotency_key", String),
            Column("result_json", Text),
            Column("created_at", String, nullable=False),
            Column("updated_at", String, nullable=False),
        )
    if entity == "idempotency":
        return Table(
            entity,
            _METADATA,
            Column("key", String, primary_key=True),
            Column("tenant_id", String, nullable=False),
            Column("entity", String, nullable=False),
            Column("record_id", Integer, nullable=False),
            Column("created_at", String, nullable=False),
        )
    if entity == "lifecycle_audit":
        return Table(
            entity,
            _METADATA,
            Column("id", Integer, primary_key=True),
            Column("tenant_id", String, nullable=False, index=True),
            Column("entity", String, nullable=False),
            Column("entity_id", Integer),
            Column("action", String, nullable=False),
            Column("created_at", String, nullable=False),
        )
    return Table(
        entity,
        _METADATA,
        Column("id", Integer, primary_key=True),
        Column("tenant_id", String, nullable=False, index=True),
        Column("reference", String),
        Column("status", String),
        Column("payload_json", Text, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    )


def db_path():
    return _db.sqlite_path()


def connect():
    return _db.connect()


def enable_wal() -> str:
    return _db.enable_wal()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _row_to_dict(entity: str, row) -> Dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    record = json.loads(mapping["payload_json"] or "{}")
    record["id"] = mapping["id"]
    record["tenant_id"] = mapping["tenant_id"]
    if "reference" in mapping and mapping["reference"] is not None:
        record.setdefault("reference", mapping["reference"])
    if "status" in mapping and mapping["status"] is not None:
        record.setdefault("status", mapping["status"])
    if "created_at" in mapping:
        record.setdefault("created_at", mapping["created_at"])
    if "updated_at" in mapping:
        record.setdefault("updated_at", mapping["updated_at"])
    if entity == "work_queue":
        payload = json.loads(mapping["payload_json"] or "{}")
        record = {
            "id": mapping["id"],
            "tenant_id": mapping["tenant_id"],
            "capability_id": mapping["capability_id"],
            "payload": payload,
            "status": mapping["status"],
            "idempotency_key": mapping["idempotency_key"],
            "result": json.loads(mapping["result_json"]) if mapping["result_json"] else None,
            "created_at": mapping["created_at"],
            "updated_at": mapping["updated_at"],
        }
    return record


def save(entity: str, record: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    table = _table(entity)
    data = dict(record or {})
    now = _now()
    values: Dict[str, Any]
    if entity == "work_queue":
        values = {
            "tenant_id": tenant_id,
            "capability_id": str(data.get("capability_id") or ""),
            "payload_json": json.dumps(data.get("payload") or {}, sort_keys=True, default=str),
            "status": str(data.get("status") or "pending"),
            "idempotency_key": data.get("idempotency_key"),
            "result_json": json.dumps(data["result"], sort_keys=True, default=str) if data.get("result") else None,
            "created_at": data.get("created_at") or now,
            "updated_at": now,
        }
    elif entity == "idempotency":
        values = {
            "key": str(data.get("key") or ""),
            "tenant_id": tenant_id,
            "entity": str(data.get("entity") or ""),
            "record_id": int(data.get("record_id") or 0),
            "created_at": data.get("created_at") or now,
        }
    elif entity == "lifecycle_audit":
        values = {
            "tenant_id": tenant_id,
            "entity": str(data.get("entity") or ""),
            "entity_id": data.get("entity_id"),
            "action": str(data.get("action") or ""),
            "created_at": data.get("created_at") or now,
        }
    else:
        values = {
            "tenant_id": tenant_id,
            "reference": data.get("reference"),
            "status": data.get("status"),
            "payload_json": json.dumps(data, sort_keys=True, default=str),
            "created_at": data.get("created_at") or now,
            "updated_at": now,
        }
    with _db.engine().begin() as conn:
        result = conn.execute(sa_insert(table).values(**values))
        new_id = result.inserted_primary_key[0]
    if entity == "idempotency":
        return dict(values)
    fetched = get(entity, int(new_id), tenant_id=tenant_id)
    return fetched if fetched is not None else {**values, "id": new_id}


def get(entity: str, record_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    table = _table(entity)
    pk = table.c.key if entity == "idempotency" else table.c.id
    with _db.engine().connect() as conn:
        row = conn.execute(
            select(table).where(pk == record_id, table.c.tenant_id == tenant_id)
        ).first()
    return _row_to_dict(entity, row) if row is not None else None


def list_all(entity: str, tenant_id: str, limit: Optional[int] = None,
             offset: int = 0) -> List[Dict[str, Any]]:
    table = _table(entity)
    query = select(table).where(table.c.tenant_id == tenant_id).order_by(table.c.id)
    if offset:
        query = query.offset(int(offset))
    if limit is not None:
        query = query.limit(int(limit))
    with _db.engine().connect() as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_dict(entity, row) for row in rows]


def update(entity: str, record_id: int, record: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    table = _table(entity)
    current = get(entity, record_id, tenant_id=tenant_id)
    if current is None:
        return None
    merged = {**current, **record}
    merged.pop("id", None)
    merged.pop("tenant_id", None)
    values = {
        "reference": merged.get("reference"),
        "status": merged.get("status"),
        "payload_json": json.dumps(merged, sort_keys=True, default=str),
        "updated_at": _now(),
    }
    with _db.engine().begin() as conn:
        conn.execute(
            sa_update(table)
            .where(table.c.id == record_id, table.c.tenant_id == tenant_id)
            .values(**values)
        )
    return get(entity, record_id, tenant_id=tenant_id)


def delete(entity: str, record_id: int, tenant_id: str) -> bool:
    table = _table(entity)
    with _db.engine().begin() as conn:
        result = conn.execute(
            sa_delete(table).where(table.c.id == record_id, table.c.tenant_id == tenant_id)
        )
    return bool(result.rowcount)


def count(entity: str, tenant_id: str) -> int:
    return len(list_all(entity, tenant_id))
