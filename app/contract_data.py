"""Source-of-record data for the Harbourline Civil Works contract.

Both entries are transcribed from the uploaded project documents and are
cited by their document id, never invented. The BOQ rates are the
customer's data: progress claims are measured against these line items.
"""

from __future__ import annotations

CONTRACT_DOCUMENT = "document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf"
BOQ_DOCUMENT = "document:a903d4ccba764b6f84b39e65b8b6add3_harbourline_boq.xlsx"

CLAUSES = {
    "8.2": "Time for Completion: 730 days from the Commencement Date.",
    "8.7": "Delay Damages: 0.1% of the Accepted Contract Amount per day of delay, capped at 10%.",
    "11.1": "Defects Notification Period: 365 days from Taking-Over.",
    "14.3": "Retention: 5% of each Interim Payment Certificate, released 50% at Taking-Over and 50% at the end of the Defects Notification Period.",
    "4.2": "Performance Security: 10% of the Accepted Contract Amount.",
}

BOQ_ITEMS = [
    {"item": "P1", "section": "Preliminaries", "description": "Site establishment & temporary facilities", "unit": "sum", "qty": 1, "rate": 185000.0},
    {"item": "P2", "section": "Preliminaries", "description": "Site security & fencing (6 months)", "unit": "month", "qty": 6, "rate": 22000.0},
    {"item": "P3", "section": "Preliminaries", "description": "Survey & setting out", "unit": "sum", "qty": 1, "rate": 48000.0},
    {"item": "P4", "section": "Preliminaries", "description": "Project signboard", "unit": "no", "qty": 2, "rate": 3500.0},
    {"item": "P5", "section": "Preliminaries", "description": "As-built documentation", "unit": "sum", "qty": 1, "rate": 26000.0},
    {"item": "E1", "section": "Earthworks", "description": "Bulk excavation to reduced level", "unit": "m3", "qty": 12500, "rate": 38.0},
    {"item": "E2", "section": "Earthworks", "description": "Disposal of surplus material off-site", "unit": "m3", "qty": 8200, "rate": 25.0},
    {"item": "E3", "section": "Earthworks", "description": "Imported granular fill, compacted", "unit": "m3", "qty": 6400, "rate": 92.0},
    {"item": "E4", "section": "Earthworks", "description": "Trench excavation for services", "unit": "m3", "qty": 1850, "rate": 55.0},
    {"item": "E5", "section": "Earthworks", "description": "Geotextile separation layer", "unit": "m2", "qty": 9600, "rate": 14.0},
]


def boq_item(item_code: str) -> dict:
    for row in BOQ_ITEMS:
        if row["item"] == str(item_code or "").upper():
            return dict(row)
    return {}


def boq_total() -> float:
    return round(sum(row["qty"] * row["rate"] for row in BOQ_ITEMS), 2)


def accepted_contract_amount(declared: float) -> float:
    value = float(declared or 0)
    return value if value > 0 else boq_total()
