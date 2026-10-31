"""Kernel formula access.

Definitions come from the Factory's universal kernel set in resolution
order; none is rewritten here. Values are supplied by the caller and a
missing named input raises rather than defaulting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.cerebrum_product_kernel.formulas.evaluator import MissingInput, safe_eval

_DEFINITIONS = Path(__file__).resolve().parents[1] / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"


def _load() -> List[Dict[str, Any]]:
    try:
        data = json.loads(_DEFINITIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [row for row in data.get("definitions") or [] if isinstance(row, dict)]


def definition(key: str) -> Dict[str, Any]:
    for row in _load():
        if row.get("key") == key or row.get("id") == key:
            return row
    raise KeyError(f"no kernel definition: {key}")


def evaluate(key: str, inputs: Dict[str, float]) -> float:
    row = definition(key)
    return float(safe_eval(str(row.get("expression") or "0"), dict(inputs)))


def markup_on_cost(price: float, unit_cost: float) -> float:
    return evaluate("universal:markup_on_cost_v1", {"price": float(price), "unit_cost": float(unit_cost)})


def gross_margin_ratio(revenue: float, cogs: float) -> float:
    return evaluate("universal:gross_margin_ratio_v1", {"revenue": float(revenue), "cogs": float(cogs)})


def tax_amount(net_amount: float, tax_rate: float) -> float:
    return evaluate("universal:tax_amount_v1", {"net_amount": float(net_amount), "tax_rate": float(tax_rate)})


__all__ = ["definition", "evaluate", "markup_on_cost", "gross_margin_ratio", "tax_amount", "MissingInput"]
