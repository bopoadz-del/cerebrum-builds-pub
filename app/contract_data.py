"""The uploaded contract excerpt and BOQ, held as data -- never re-invented.

Every figure in this module is transcribed from the two uploaded documents the
platform was given. Capabilities cite these constants and the document ids
below; a handler never restates a clause value from memory.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CONTRACT_DOCUMENT = "document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf"
BOQ_DOCUMENT = "document:9eef45a732d042dfb83157ec67068a75_harbourline_boq.xlsx"

CLAUSES: Dict[str, str] = {
    "8.2": "Time for Completion: 730 days from the Commencement Date.",
    "8.7": (
        "Delay Damages: 0.1% of the Accepted Contract Amount per day of delay, "
        "capped at 10% of the Accepted Contract Amount."
    ),
    "11.1": "Defects Notification Period: 365 days from Taking-Over.",
    "14.3": (
        "Retention: 5% of each Interim Payment Certificate, released 50% at "
        "Taking-Over and 50% at the end of the Defects Notification Period."
    ),
    "4.2": "Performance Security: 10% of the Accepted Contract Amount.",
}

TIME_FOR_COMPLETION_DAYS = 730
DELAY_DAMAGES_RATE_PCT = 0.1
DELAY_DAMAGES_CAP_PCT = 10.0
RETENTION_PCT = 5.0
RETENTION_RELEASE_AT_TAKING_OVER = 50.0
RETENTION_RELEASE_AT_DNP_END = 50.0
DEFECTS_NOTIFICATION_DAYS = 365
PERFORMANCE_SECURITY_RATE_PCT = 10.0

#: (item, section, description, unit, quantity, rate_sar)
BOQ_ROWS: List[Tuple[str, str, str, str, float, float]] = [
    ("P1", "Preliminaries", "Site establishment & temporary facilities", "sum", 1, 185000),
    ("P2", "Preliminaries", "Site security & fencing (6 months)", "month", 6, 22000),
    ("P3", "Preliminaries", "Survey & setting out", "sum", 1, 48000),
    ("P4", "Preliminaries", "Project signboard", "no", 2, 3500),
    ("P5", "Preliminaries", "As-built documentation", "sum", 1, 26000),
    ("E1", "Earthworks", "Bulk excavation to reduced level", "m3", 12500, 38),
    ("E2", "Earthworks", "Disposal of surplus material off-site", "m3", 8200, 25),
    ("E3", "Earthworks", "Imported granular fill, compacted", "m3", 6400, 92),
    ("E4", "Earthworks", "Trench excavation for services", "m3", 1850, 55),
    ("E5", "Earthworks", "Geotextile separation layer", "m2", 9600, 14),
]

BOQ_ITEMS: Dict[str, Dict[str, Any]] = {
    item: {
        "item": item,
        "section": section,
        "description": description,
        "unit": unit,
        "quantity": float(quantity),
        "rate": float(rate),
        "amount": round(float(quantity) * float(rate), 2),
        "source_document": BOQ_DOCUMENT,
    }
    for item, section, description, unit, quantity, rate in BOQ_ROWS
}

ACCEPTED_CONTRACT_AMOUNT = round(sum(row["amount"] for row in BOQ_ITEMS.values()), 2)


def clause_text(ref: str) -> str:
    return CLAUSES.get(str(ref or "").strip(), "")


def boq_item(item: str) -> Optional[Dict[str, Any]]:
    return BOQ_ITEMS.get(str(item or "").strip().upper())


def boq_total() -> float:
    return ACCEPTED_CONTRACT_AMOUNT


def boq_lines() -> List[Dict[str, Any]]:
    return [dict(row) for row in BOQ_ITEMS.values()]


def contract_source_text() -> str:
    """The contract excerpt as searchable text, with each clause labelled."""
    return "\n".join(f"Clause {ref} {text}" for ref, text in CLAUSES.items())


def write_boq_csv(directory: Path, stem: str = "harbourline_boq") -> Path:
    """Materialise the uploaded BOQ as a CSV the boq_processor block can read."""
    path = Path(directory) / (str(stem) + ".csv")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Item", "Description", "Unit", "Qty", "Rate (SAR)"])
        for item, section, description, unit, quantity, rate in BOQ_ROWS:
            writer.writerow([item, description, unit, quantity, rate])
    return path


def write_boq_xlsx(directory: Path, stem: str = "harbourline_boq") -> Path:
    """Materialise the uploaded BOQ as an XLSX the pdf/document blocks can read."""
    from openpyxl import Workbook

    path = Path(directory) / (str(stem) + ".xlsx")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BOQ"
    sheet.append(["Item", "Description", "Unit", "Qty", "Rate (SAR)"])
    for item, section, description, unit, quantity, rate in BOQ_ROWS:
        sheet.append([item, description, unit, quantity, rate])
    workbook.save(path)
    return path


def record_text(record: Dict[str, Any]) -> str:
    """A citable summary of one record, used as a document body."""
    parts = [f"{key}: {value}" for key, value in (record or {}).items() if value not in (None, "")]
    return "\n".join(parts)
