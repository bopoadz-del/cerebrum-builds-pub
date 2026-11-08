"""The uploaded contract and BOQ, held as this platform's source of record.

Every figure a capability uses is traceable to one of the two uploaded
documents: the contract excerpt or the bill of quantities. The documents are
read from ``corpus/source_of_record.json`` by ``app.sources``; this module is
the capability-facing view of that same data. Nothing here invents a rate: a
value that is not in the documents is refused by the capability that needs it.

READS   corpus/source_of_record.json (through app.sources) and the declared
        locale for the money label.
WRITES  nothing -- this module is a read-only record of the source documents.
NEVER   invents a clause, a BOQ item, a quantity or a rate.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from app import sources

__all__ = [
    "BOQ_DOCUMENT",
    "CONTRACT_DOCUMENT",
    "CLAUSES",
    "TIME_FOR_COMPLETION_DAYS",
    "DELAY_DAMAGES_DAILY_PCT",
    "DELAY_DAMAGES_CAP_PCT",
    "DEFECTS_NOTIFICATION_DAYS",
    "RETENTION_PCT",
    "RETENTION_RELEASE_SPLIT_PCT",
    "PERFORMANCE_SECURITY_PCT",
    "boq_lines",
    "boq_item",
    "boq_total",
    "clause",
    "clause_number",
    "contract_source_text",
    "currency_label",
    "write_boq_csv",
]

CONTRACT_DOCUMENT = sources.CONTRACT_DOCUMENT
BOQ_DOCUMENT = sources.BOQ_DOCUMENT

#: The contract's own terms, read from the source-of-record data file.
TIME_FOR_COMPLETION_DAYS = int(sources.term("time_for_completion_days", 0))
DELAY_DAMAGES_DAILY_PCT = float(sources.term("delay_damages_daily_pct", 0.0))
DELAY_DAMAGES_CAP_PCT = float(sources.term("delay_damages_cap_pct", 0.0))
DEFECTS_NOTIFICATION_DAYS = int(sources.term("defects_notification_days", 0))
RETENTION_PCT = float(sources.term("retention_pct", 0.0))
RETENTION_RELEASE_SPLIT_PCT = float(sources.term("retention_release_split_pct", 0.0))
PERFORMANCE_SECURITY_PCT = float(sources.term("performance_security_pct", 0.0))


def _clauses() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in sources.CLAUSES:
        number = str(row.get("clause") or "")
        out[number] = {
            "label": str(row.get("subject") or ""),
            "text": str(row.get("terms") or ""),
            "key": str(row.get("key") or ""),
            "document": CONTRACT_DOCUMENT,
        }
    return out


CLAUSES: Dict[str, Dict[str, Any]] = _clauses()


def clause_number(key: str) -> str:
    """The number the contract states for a clause key, never typed here."""
    return sources.clause_number(key)


def boq_lines() -> List[Dict[str, Any]]:
    """Every BOQ line, with its amount derived from quantity x rate."""
    return sources.boq_lines()


def boq_item(code: str) -> Optional[Dict[str, Any]]:
    """One BOQ line by its item code, or None when the code is not in the BOQ."""
    return sources.boq_item(code)


def boq_total() -> float:
    """The Accepted Contract Amount implied by the uploaded BOQ."""
    return sources.boq_total()


def clause(ref: str) -> Optional[Dict[str, Any]]:
    return CLAUSES.get(str(ref or "").strip())


def contract_source_text() -> str:
    """The contract excerpt as one citable block of text."""
    return sources.contract_source_text()


def currency_label() -> str:
    """The declared currency, read from app.money_settings at point of use.

    With no declared currency the money figures are still computed, but the
    label says WITHHELD rather than choosing a currency the brief did not give.
    """
    from app import money_settings

    try:
        return money_settings.currency()
    except Exception:
        return "WITHHELD (no currency declared)"


def write_boq_csv(directory: Path, stem: str = "boq") -> Path:
    """Materialise the uploaded BOQ as a CSV the boq_processor block parses."""
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    path = directory / f"{stem}.csv"
    columns = sources.BOQ_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                columns.get("item", "Item"),
                columns.get("description", "Description"),
                columns.get("unit", "Unit"),
                columns.get("quantity", "Qty"),
                columns.get("rate", "Rate"),
            ]
        )
        for line in boq_lines():
            writer.writerow(
                [
                    line["item"],
                    line["description"],
                    line["unit"],
                    line["quantity"],
                    line["rate"],
                ]
            )
    return path
