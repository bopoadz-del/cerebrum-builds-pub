"""The uploaded project documents, read as the platform's source of record.

The contract excerpt and the BOQ schedule are DATA, transcribed once into
corpus/source_of_record.json from the two documents the customer uploaded.
This module only indexes that data; no document text and no rate is a value
in code, and every figure is cited as document:<filename>.

Scope READS: corpus/source_of_record.json.
Scope WRITES: nothing -- the source is read-only.
Scope NEVER: no network, no document that was not uploaded.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "corpus" / "source_of_record.json"


def _load() -> Dict[str, Any]:
    try:
        data = json.loads(_SOURCE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


_DATA = _load()
_PROJECT = _DATA.get("project") or {}
_DOCS = _PROJECT.get("documents") or {}

CONTRACT_DOCUMENT = str(_DOCS.get("contract") or "")
BOQ_DOCUMENT = str(_DOCS.get("boq") or "")
CONTRACT_FILENAME = CONTRACT_DOCUMENT.split("document:", 1)[-1]
BOQ_FILENAME = BOQ_DOCUMENT.split("document:", 1)[-1]
PROJECT_NAME = str(_PROJECT.get("name") or "project")
BOQ_CURRENCY = str(_PROJECT.get("currency") or "")
BOQ_HEADER = str(_PROJECT.get("currency_header") or "rate")

CONTRACT_CLAUSES: List[Dict[str, Any]] = [
    dict(item) for item in (_DATA.get("clauses") or []) if isinstance(item, dict)
]
BOQ_ITEMS: List[Dict[str, Any]] = [
    dict(item) for item in (_DATA.get("boq") or []) if isinstance(item, dict)
]


def contract_text() -> str:
    """The uploaded contract excerpt, as read, with its citation."""
    lines = [
        "%s - contract excerpt" % PROJECT_NAME,
        "source: %s" % CONTRACT_DOCUMENT,
        "",
    ]
    for clause in CONTRACT_CLAUSES:
        lines.append("clause %s  %s" % (clause.get("clause"), clause.get("text")))
    return "\n".join(lines) + "\n"


def boq_csv() -> str:
    """The BOQ schedule as CSV, headed by the rate-column currency declaration."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["item", "description", "unit", "qty", BOQ_HEADER])
    for section in dict.fromkeys(item.get("section") for item in BOQ_ITEMS):
        writer.writerow(["# " + str(section)])
        for item in BOQ_ITEMS:
            if item.get("section") != section:
                continue
            writer.writerow(
                [
                    item.get("item"),
                    item.get("description"),
                    item.get("unit"),
                    item.get("qty"),
                    item.get("rate"),
                ]
            )
    return buffer.getvalue()


def boq_rows() -> List[Dict[str, Any]]:
    return [dict(item) for item in BOQ_ITEMS]


def boq_item(code: Any) -> Optional[Dict[str, Any]]:
    wanted = str(code or "").strip().upper()
    for item in BOQ_ITEMS:
        if str(item.get("item", "")).upper() == wanted:
            return dict(item)
    return None


def clause(ref: Any) -> Optional[Dict[str, Any]]:
    wanted = str(ref or "").strip()
    for item in CONTRACT_CLAUSES:
        if str(item.get("clause")) == wanted:
            return dict(item)
    return None


def clause_by_key(key: Any) -> Optional[Dict[str, Any]]:
    wanted = str(key or "").strip().lower()
    for item in CONTRACT_CLAUSES:
        if str(item.get("key")).lower() == wanted:
            return dict(item)
    return None


def clause_number(key: str) -> str:
    found = clause_by_key(key)
    return str(found.get("clause")) if found else str(key)


def clause_value(key: str) -> float:
    found = clause_by_key(key)
    if found is None:
        raise ValueError("unknown contract term: %s" % key)
    return float(found.get("value"))


def accepted_contract_amount() -> float:
    total = 0.0
    for item in BOQ_ITEMS:
        total += float(item.get("qty") or 0) * float(item.get("rate") or 0)
    return round(total, 2)


def boq_total() -> float:
    return accepted_contract_amount()


def line_count() -> int:
    return len(BOQ_ITEMS)


def citations() -> Dict[str, str]:
    return {
        "contract": CONTRACT_DOCUMENT,
        "boq": BOQ_DOCUMENT,
    }
