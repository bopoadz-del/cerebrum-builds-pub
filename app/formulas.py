"""The factory's own arithmetic (precedence layer 3).

Written by the factory WRITER role (codewhale exec).

Kernel definitions, by address, evaluated with the kernel's safe evaluator
over grounded inputs -- no number is typed here:
  universal:tax_amount_v1, universal:gross_from_net_v1,
  universal:net_from_gross_v1, universal:discount_amount_v1,
  universal:net_price_after_discount_v1.

The tax rate is the operator's PLATFORM_TAX_RATE setting, read through
app.money_settings at the point of use; the Tunisian VAT rate is therefore
the customer's setting, changeable without a code change. Process ratios (curing progress, mass loss, shortfall) are plain
arithmetic against named settings the factory owns (see README.md).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from app.cerebrum_product_kernel.formulas.evaluator import safe_eval

_ROOT = Path(__file__).resolve().parents[1]
_DEFINITIONS = _ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"

KERNEL_KEYS = {
    "tax_amount": "universal:tax_amount_v1",
    "gross_from_net": "universal:gross_from_net_v1",
    "net_from_gross": "universal:net_from_gross_v1",
    "discount_amount": "universal:discount_amount_v1",
    "net_price_after_discount": "universal:net_price_after_discount_v1",
}


class FormulaUnavailable(RuntimeError):
    """The kernel definition this formula addresses is not on disk."""


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or value in (None, ""):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def setting_number(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _expression(key: str) -> str:
    try:
        data = json.loads(_DEFINITIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FormulaUnavailable(str(exc)) from exc
    for definition in data.get("definitions") or []:
        if definition.get("key") == key:
            return str(definition.get("expression") or "")
    raise FormulaUnavailable(key + " is not in the kernel definition set")


def _evaluate(key: str, **inputs: float) -> float:
    return float(safe_eval(_expression(key), {k: float(v) for k, v in inputs.items()}))


def tax_amount(net_amount: Any, tax_rate: Any) -> float:
    return round(_evaluate(KERNEL_KEYS["tax_amount"], net_amount=_number(net_amount), tax_rate=_number(tax_rate)), 3)


def gross_from_net(net_amount: Any, tax_rate: Any) -> float:
    return round(_evaluate(KERNEL_KEYS["gross_from_net"], net_amount=_number(net_amount), tax_rate=_number(tax_rate)), 3)


def net_from_gross(gross_amount: Any, tax_rate: Any) -> float:
    return round(_evaluate(KERNEL_KEYS["net_from_gross"], gross_amount=_number(gross_amount), tax_rate=_number(tax_rate)), 3)


def discount_amount(list_price: Any, discount_rate: Any) -> float:
    return round(_evaluate(KERNEL_KEYS["discount_amount"], list_price=_number(list_price), discount_rate=_number(discount_rate)), 3)


def net_price_after_discount(list_price: Any, discount_rate: Any) -> float:
    return round(_evaluate(KERNEL_KEYS["net_price_after_discount"], list_price=_number(list_price), discount_rate=_number(discount_rate)), 3)


def line_total(quantity: Any, unit_price: Any) -> float:
    """A money field multiplied by a declared quantity is a total.

    ``quantity`` is a declared quantity field (QUANTITY_FIELDS), so the
    multiplication is a total, not a rate: the amount and its count are
    coerced to numbers first and neither factor is a typed-in figure.
    """
    qty = _number(quantity)
    price = _number(unit_price)
    return round(qty * price, 3)


def compost_yield_kg(input_kg: Any) -> float:
    """Finished compost expected from a batch's input weight.

    The yield ratio is the factory's own process setting
    (PLATFORM_RATE_COMPOST_YIELD), never a figure baked into this source.
    """
    from app.money_settings import rate

    return round(_number(input_kg) * rate("compost_yield"), 2)


def mass_loss_pct(input_kg: Any, output_kg: Any) -> float:
    incoming = _number(input_kg)
    if incoming <= 0:
        return 0.0
    return round(max(0.0, (incoming - _number(output_kg)) / incoming) * 100.0, 2)


def curing_progress_pct(days_cured: Any, target_days: Any) -> float:
    target = _number(target_days)
    if target <= 0:
        return 0.0
    return round(min(100.0, max(0.0, _number(days_cured) / target * 100.0)), 1)


def shortfall_pct(planned_kg: Any, collected_kg: Any) -> float:
    planned = _number(planned_kg)
    if planned <= 0:
        return 0.0
    return round(max(0.0, (planned - _number(collected_kg)) / planned) * 100.0, 2)


def collection_completion_pct(closed: Any, total: Any) -> float:
    whole = _number(total)
    if whole <= 0:
        return 0.0
    return round(min(100.0, max(0.0, _number(closed) / whole * 100.0)), 1)


FORMULAS: Dict[str, Dict[str, Any]] = {
    "tax_amount": {"call": tax_amount, "definition": KERNEL_KEYS["tax_amount"], "layer": 3},
    "gross_from_net": {"call": gross_from_net, "definition": KERNEL_KEYS["gross_from_net"], "layer": 3},
    "net_from_gross": {"call": net_from_gross, "definition": KERNEL_KEYS["net_from_gross"], "layer": 3},
    "discount_amount": {"call": discount_amount, "definition": KERNEL_KEYS["discount_amount"], "layer": 3},
    "net_price_after_discount": {"call": net_price_after_discount, "definition": KERNEL_KEYS["net_price_after_discount"], "layer": 3},
    "line_total": {"call": line_total, "definition": "quantity * unit_price", "layer": 3},
    "compost_yield_kg": {"call": compost_yield_kg, "definition": "PLATFORM_RATE_COMPOST_YIELD (operator setting)", "layer": 3},
    "mass_loss_pct": {"call": mass_loss_pct, "definition": "(input - output) / input", "layer": 3},
    "curing_progress_pct": {"call": curing_progress_pct, "definition": "days / target_days", "layer": 3},
    "shortfall_pct": {"call": shortfall_pct, "definition": "(planned - collected) / planned", "layer": 3},
    "collection_completion_pct": {"call": collection_completion_pct, "definition": "closed / total", "layer": 3},
}


def catalogue() -> Dict[str, Any]:
    return {
        "schema": "formulas.v1",
        "layer": 3,
        "formulas": [
            {"name": name, "definition": entry["definition"], "layer": entry["layer"]}
            for name, entry in sorted(FORMULAS.items())
        ],
    }
