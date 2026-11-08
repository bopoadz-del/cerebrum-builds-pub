"""Deterministic contract arithmetic, resolved against the kernel first.

FORMULA SOURCES, in resolution order:
1. the kernel definitions under ``app/cerebrum_product_kernel/formulas`` --
   ``discount_amount`` (used for retention and performance security) and
   ``late_fee_simple`` (used for delay damages);
2. Store coverage for this vertical: none;
3. improvised: ``delay_damages_capped`` -- the kernel has no capped
   delay-damages identity, so this row is "improvised, no Store coverage",
   with its source (Clause 8.7 of the uploaded contract) cited in
   ``writer_definitions.jsonl`` and docs/provenance/provenance.json.

READS   the request's figures and the kernel definition set.
WRITES  nothing -- pure functions.
NEVER   invents a rate, a cap or a day-count: every value is a named input.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.cerebrum_product_kernel.formulas import load_base_definitions
from app.cerebrum_product_kernel.formulas.evaluator import safe_eval

#: address -> definition, from the kernel's own base set.
_BASE: Optional[Dict[str, Any]] = None


def _definitions() -> Dict[str, Any]:
    global _BASE
    if _BASE is None:
        base = load_base_definitions()
        _BASE = {row["key"]: row for row in base.get("definitions", [])}
    return _BASE


def evaluate(address: str, values: Dict[str, float]) -> float:
    """Evaluate one kernel definition by its address."""
    definition = _definitions().get(address)
    if definition is None:
        raise KeyError(f"no kernel definition at {address}")
    return float(safe_eval(definition["expression"], dict(values)))


def round_money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def discount_amount(amount: float, rate_pct: float) -> float:
    """A percentage of an amount, via universal:discount_amount_v1."""
    return round_money(
        evaluate(
            "universal:discount_amount_v1",
            {"list_price": float(amount), "discount_rate": float(rate_pct) / 100.0},
        )
    )


def retention_amount(gross_amount: float, retention_pct: float) -> float:
    """Clause 14.3 retention: a percentage of the certificate."""
    return discount_amount(gross_amount, retention_pct)


def performance_security(accepted_contract_amount: float, rate_pct: float) -> float:
    """Clause 4.2 performance security: a percentage of the Accepted Contract Amount."""
    return discount_amount(accepted_contract_amount, rate_pct)


def retention_release(retention_held: float, split_pct: float = 50.0) -> Dict[str, float]:
    """Clause 14.3 release: 50% at Taking-Over, the remainder at DNP end."""
    at_taking_over = discount_amount(retention_held, split_pct)
    return {
        "at_taking_over": at_taking_over,
        "at_dnp_end": round_money(retention_held - at_taking_over),
    }


# NOTE: delay_damages_capped is "improvised, no Store coverage". The kernel
# supplies the simple per-day fee identity (universal:late_fee_simple_v1);
# the 10% cap is Clause 8.7 and has no kernel definition. Every rate and the
# day-count convention remain inputs; none is typed into the expression.
def delay_damages(
    accepted_contract_amount: float,
    daily_rate_pct: float,
    delay_days: int,
    cap_pct: float,
    days_in_year: int = 365,
) -> Dict[str, float]:
    """Clause 8.7 delay damages: per-day fee capped at a percentage of the ACA.

    Source: Clause 8.7 of the uploaded contract, document:harbourline_contract.pdf
    ("0.1% of the Accepted Contract Amount per day of delay, capped at 10%").
    """
    days = max(0, int(delay_days))
    annual_rate = (float(daily_rate_pct) / 100.0) * float(days_in_year)
    uncapped = evaluate(
        "universal:late_fee_simple_v1",
        {
            "overdue_amount": float(accepted_contract_amount),
            "annual_rate": annual_rate,
            "days_overdue": float(days),
            "days_in_year": float(days_in_year),
        },
    )
    cap = discount_amount(accepted_contract_amount, cap_pct)
    damages = round_money(min(uncapped, cap))
    return {
        "uncapped": round_money(uncapped),
        "cap": cap,
        "damages": damages,
        "cap_reached": round_money(uncapped) >= cap,
    }


def net_certificate(gross_amount: float, retention: float, security: float) -> float:
    return round_money(max(0.0, float(gross_amount) - float(retention) - float(security)))


IMPROVISED = {
    "delay_damages_capped": {
        "id": "delay_damages_capped",
        "label": "improvised, no Store coverage -- capped delay damages (Clause 8.7)",
        "source": "improvised, no Store coverage -- Clause 8.7 of document:harbourline_contract.pdf",
    }
}
