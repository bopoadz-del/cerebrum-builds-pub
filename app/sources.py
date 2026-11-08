"""The uploaded contract and BOQ, read from the source-of-record data file.

The customer's two documents are authority for every figure this platform
computes. They are shipped as data beside the code (``corpus/source_of_record.json``
-- the same content the customer uploaded), cited by their document ids, and
loaded here at import. No clause number, BOQ rate or document name is typed
into Python: the data file is the source, this module is the reader.

READS   corpus/source_of_record.json.
WRITES  nothing -- this module is a read-only record of the source documents.
NEVER   invents a clause, a BOQ item, a quantity or a rate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = _ROOT / "corpus" / "source_of_record.json"

with SOURCE_PATH.open(encoding="utf-8") as _handle:
    SOURCE: Dict[str, Any] = json.load(_handle)

PROJECT: Dict[str, Any] = dict(SOURCE.get("project") or {})
PROJECT_KEY = str(PROJECT.get("key") or "")
PROJECT_NAME = str(PROJECT.get("name") or "")
PRODUCT_ID = str(PROJECT.get("product_id") or PROJECT_KEY or "platform")
CONTRACT_TITLE = str(PROJECT.get("title") or PROJECT_NAME)

_DOCUMENTS: Dict[str, str] = dict(SOURCE.get("documents") or {})
CONTRACT_DOCUMENT = str(_DOCUMENTS.get("contract") or "")
BOQ_DOCUMENT = str(_DOCUMENTS.get("boq") or "")

CLAUSES: List[Dict[str, Any]] = [
    dict(row) for row in (SOURCE.get("clauses") or []) if isinstance(row, dict)
]
TERMS: Dict[str, Any] = dict(SOURCE.get("terms") or {})
BOQ_COLUMNS: Dict[str, Any] = dict(SOURCE.get("boq_columns") or {})

BOQ_ITEMS: List[Dict[str, Any]] = []
for _section in SOURCE.get("boq_sections") or []:
    if not isinstance(_section, dict):
        continue
    for _row in _section.get("items") or []:
        if isinstance(_row, dict):
            BOQ_ITEMS.append({**_row, "section": str(_section.get("section") or "")})


def clause(key: str) -> Optional[Dict[str, Any]]:
    """The clause whose stable key or number is ``key``; None when absent."""
    wanted = str(key or "").strip().lower()
    for row in CLAUSES:
        if str(row.get("key") or "").strip().lower() == wanted:
            return row
        if str(row.get("clause") or "").strip() == wanted:
            return row
    return None


def clause_number(key: str) -> str:
    """The clause number the contract states for ``key``, never typed in code."""
    return str((clause(key) or {}).get("clause") or "")


def clause_numbers() -> List[str]:
    return [str(row.get("clause") or "") for row in CLAUSES]


def term(name: str, default: Any = None) -> Any:
    return TERMS.get(name, default)


def boq_lines() -> List[Dict[str, Any]]:
    """Every BOQ line, with its amount derived from quantity x rate."""
    lines: List[Dict[str, Any]] = []
    for row in BOQ_ITEMS:
        quantity = float(row.get("quantity") or 0.0)
        rate = float(row.get("rate") or 0.0)
        lines.append(
            {
                "item": str(row.get("item") or ""),
                "description": str(row.get("description") or ""),
                "unit": str(row.get("unit") or ""),
                "quantity": quantity,
                "rate": rate,
                "amount": round(quantity * rate, 2),
                "section": str(row.get("section") or ""),
                "document": BOQ_DOCUMENT,
            }
        )
    return lines


def boq_item(code: str) -> Optional[Dict[str, Any]]:
    wanted = str(code or "").strip().upper()
    for line in boq_lines():
        if line["item"] == wanted:
            return line
    return None


def boq_total() -> float:
    return round(sum(line["amount"] for line in boq_lines()), 2)


def contract_source_text() -> str:
    """The contract excerpt as one citable block of text."""
    body = "\n".join(
        f"Clause {row.get('clause')}  {row.get('subject')}: {row.get('terms')}"
        for row in CLAUSES
    )
    return CONTRACT_TITLE + "\n" + body
