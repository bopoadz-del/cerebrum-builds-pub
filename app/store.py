"""SQLite persist rooted at STORAGE_PATH. Tables match spec.entity / alembic 0001."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.schema import SPECS

COLUMNS: Dict[str, List[str]] = {
    spec["entity"]: ["reference", "status", "payload_json"] for spec in SPECS.values()
}

_local = threading.local()


def storage_root() -> Path:
    root = Path(os.environ.get("STORAGE_PATH") or "./data").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> Path:
    return storage_root() / "platform.db"


def _connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    path = str(db_path())
    if conn is None or getattr(_local, "path", None) != path:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        path_obj = db_path()
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path_obj), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        _local.path = path
    return conn


def reset_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    _local.conn = None
    _local.path = None


def ensure_schema() -> None:
    conn = _connect()
    cur = conn.cursor()
    for entity, cols in COLUMNS.items():
        col_sql = ", ".join(f"{name} TEXT" for name in cols)
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {entity} ("
            f"pk INTEGER PRIMARY KEY AUTOINCREMENT, {col_sql})"
        )
    conn.commit()


def save(entity: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if entity not in COLUMNS:
        raise ValueError(f"unknown entity: {entity}")
    ensure_schema()
    record = {
        "reference": str(payload.get("reference", "")),
        "status": str(payload.get("status", "open")),
        "payload_json": json.dumps(payload, default=str),
    }
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {entity} (reference, status, payload_json) VALUES (?, ?, ?)",
        (record["reference"], record["status"], record["payload_json"]),
    )
    conn.commit()
    return {**payload, "entity": entity}


def list_all(entity: str) -> List[Dict[str, Any]]:
    if entity not in COLUMNS:
        raise ValueError(f"unknown entity: {entity}")
    ensure_schema()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"SELECT reference, status, payload_json FROM {entity} ORDER BY pk")
    rows = []
    for row in cur.fetchall():
        try:
            body = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            body = {}
        if not isinstance(body, dict):
            body = {"value": body}
        body.setdefault("reference", row["reference"])
        body.setdefault("status", row["status"])
        rows.append(body)
    return rows
