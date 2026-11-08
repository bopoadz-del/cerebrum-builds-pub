"""Formula resolution and evaluation.

Resolution order: the kernel's universal definitions first, then (for this
vertical) nothing in the Store, and only then an improvised definition. The
definitions used by this platform are all kernel base-tier identities; the
the contract supplies the rates they are applied with, parsed from its own
text; no rate is baked into this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.contract_terms import (
    CLAUSES,
    DELAY_DAMAGES,
    DELAY_DAMAGES_CAP_RATIO,
    DELAY_DAMAGES_RATE_PER_DAY,
    PERFORMANCE_SECURITY,
    PERFORMANCE_SECURITY_RATIO,
    RETENTION,
    RETENTION_RATIO,
)
from app.cerebrum_product_kernel.formulas.evaluator import MissingInput, safe_eval

_DEFINITIONS = (
    Path(__file__).resolve().parent
    / "cerebrum_product_kernel"
    / "formulas"
    / "universal_definitions.json"
)


class FormulaNotCovered(KeyError):
    """No kernel (and no Store) definition covers this calculation."""


def _load() -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(_DEFINITIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for definition in payload.get("definitions") or []:
        if not isinstance(definition, dict):
            continue
        for key in (definition.get("id"), definition.get("key")):
            if key:
                out[str(key)] = definition
    return out


DEFINITIONS = _load()


def definition(identifier: str) -> Dict[str, Any]:
    found = DEFINITIONS.get(str(identifier or ""))
    if found is None:
        raise FormulaNotCovered(identifier)
    return found


def evaluate(identifier: str, inputs: Dict[str, float]) -> Dict[str, Any]:
    """Evaluate a kernel definition over grounded inputs."""
    found = definition(identifier)
    for guard in found.get("guards") or []:
        name = str(guard).split("!=")[0].strip()
        if name and name not in inputs:
            raise MissingInput(name)
    value = safe_eval(str(found.get("expression") or ""), {k: float(v) for k, v in inputs.items()})
    return {
        "definition": found.get("id"),
        "key": found.get("key"),
        "expression": found.get("expression"),
        "inputs": dict(inputs),
        "value": float(value),
        "tier": found.get("tier"),
        "authority_layer": "formulas",
    }


def delay_damages(accepted_contract_amount: float, delay_days: float) -> Dict[str, Any]:
    """The delay-damages clause: the daily percentage and the cap come from the contract.

    The kernel identity is ``late_fee_simple`` over a one-day year, which is
    the per-day form the clause states. The rate and the cap are the contract
    terms, read from app.contract_terms, not defaults in this module.
    """
    raw = evaluate(
        "late_fee_simple",
        {
            "overdue_amount": max(0.0, float(accepted_contract_amount)),
            "annual_rate": DELAY_DAMAGES_RATE_PER_DAY,
            "days_overdue": max(0.0, float(delay_days)),
            "days_in_year": 1.0,
        },
    )
    cap = max(0.0, float(accepted_contract_amount)) * DELAY_DAMAGES_CAP_RATIO
    capped = min(raw["value"], cap)
    return {
        **raw,
        "uncapped_value": raw["value"],
        "cap": cap,
        "value": capped,
        "capped": raw["value"] > cap,
        "clause": DELAY_DAMAGES,
    }


def retention(interim_payment_amount: float) -> Dict[str, Any]:
    """The retention clause ratio from the contract."""
    amount = max(0.0, float(interim_payment_amount))
    return {
        "definition": "retention_ratio",
        "clause": RETENTION,
        "rate": RETENTION_RATIO,
        "value": amount * RETENTION_RATIO,
        "authority_layer": "formulas",
        "source": "arithmetic over the parsed retention rate in app.contract_terms",
    }


def performance_security_requirement(accepted_contract_amount: float) -> Dict[str, Any]:
    """The performance-security ratio from the contract."""
    amount = max(0.0, float(accepted_contract_amount))
    return {
        "definition": "performance_security_ratio",
        "clause": PERFORMANCE_SECURITY,
        "rate": PERFORMANCE_SECURITY_RATIO,
        "value": amount * PERFORMANCE_SECURITY_RATIO,
        "authority_layer": "formulas",
        "source": "arithmetic over the parsed performance-security rate in app.contract_terms",
    }


def prorate(amount: float, used: float, period: float) -> Dict[str, Any]:
    return evaluate("proration", {"amount": amount, "days_used": used, "days_in_period": period})


def catalogue() -> List[Dict[str, Any]]:
    return [
        {
            "id": key,
            "name": value.get("name"),
            "expression": value.get("expression"),
            "tier": value.get("tier"),
        }
        for key, value in sorted(DEFINITIONS.items())
        if key == value.get("id")
    ]


def clause_rate(clause: str) -> Optional[float]:
    entry = CLAUSES.get(str(clause))
    return entry.get("rate_per_day") if entry else None
