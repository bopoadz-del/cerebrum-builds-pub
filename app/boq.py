"""Bill of Quantities parsing, in the standard library.

The uploaded BOQ is the source of record for quantities and rates.  Its rows
are tab- or comma-separated (``Item, Description, Unit, Qty, Rate``); a row
whose quantity or rate is not a number is kept as an unparsed row rather than
silently priced as zero, so the certificate can say what it refused.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List

_HEADER_HINTS = ("item", "description", "unit", "qty", "quantity", "rate", "amount")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _clean(value: Any) -> str:
    return str(value or "").strip().strip('"')


def _number(value: Any) -> float | None:
    text = _clean(value).replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _looks_like_header(cells: List[str]) -> bool:
    lowered = [c.lower() for c in cells]
    hits = sum(1 for hint in _HEADER_HINTS if any(hint in cell for cell in lowered))
    return hits >= 3


def parse_rows(text: str) -> List[Dict[str, Any]]:
    """Rows of a BOQ extract: item, description, unit, quantity, rate."""
    body = str(text or "").strip()
    if not body:
        return []
    sample = body.splitlines()[0]
    delimiter = "\t" if "\t" in sample else ","
    rows: List[Dict[str, Any]] = []
    for cells in csv.reader(io.StringIO(body), delimiter=delimiter):
        cells = [_clean(cell) for cell in cells]
        if not any(cells):
            continue
        if cells[0].startswith("#") or _looks_like_header(cells):
            continue
        item = cells[0]
        if not item:
            continue
        description = cells[1] if len(cells) > 1 else ""
        unit = cells[2] if len(cells) > 2 else ""
        quantity = _number(cells[3]) if len(cells) > 3 else None
        rate = _number(cells[4]) if len(cells) > 4 else None
        amount = _number(cells[5]) if len(cells) > 5 else None
        if amount is None and quantity is not None and rate is not None:
            amount = round(quantity * rate, 2)
        rows.append(
            {
                "item": item,
                "description": description,
                "unit": unit,
                "quantity": quantity,
                "rate": rate,
                "amount": amount,
                "priced": quantity is not None and rate is not None,
            }
        )
    return rows


def line_for(text: str, item_code: str) -> Dict[str, Any] | None:
    """The BOQ line a certificate names, or None when the bill omits it."""
    wanted = str(item_code or "").strip().lower()
    if not wanted:
        return None
    for row in parse_rows(text):
        if str(row.get("item") or "").strip().lower() == wanted:
            return row
    return None


def total(text: str) -> Dict[str, Any]:
    rows = parse_rows(text)
    priced = [row for row in rows if row.get("amount") is not None]
    return {
        "items": len(rows),
        "priced_items": len(priced),
        "unpriced_items": [row["item"] for row in rows if row.get("amount") is None],
        "total": round(sum(float(row["amount"]) for row in priced), 2),
    }
