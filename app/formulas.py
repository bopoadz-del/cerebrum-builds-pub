"""Formulas the contracts-administration capabilities compute.

Every figure here is either a kernel definition (evaluated through
``app.cerebrum_product_kernel.formulas.evaluator``) or an improvised
definition with no Store coverage, labelled as such in its docstring and in
the answer it produces. Rates and percentages are never typed in: they are
read from the uploaded contract through ``app.contract_data`` or supplied by
the caller.
"""

from __future__ import annotations

from typing import Any, Dict

from app.cerebrum_product_kernel.formulas.evaluator import safe_eval

IMPROVISED = "improvised, no Store coverage"

#: One row per formula this product contributes (prompt OUTPUT contract).
WRITER_DEFINITIONS = (
    {
        "id": "delay_damages_capped",
        "label": "Delay damages at a daily percentage, capped at a percentage of the amount",
        "source": IMPROVISED + " -- derived from document:harbourline_contract.pdf Clause 8.7",
    },
    {
        "id": "retention_amount",
        "label": "Retention withheld from an interim payment certificate",
        "source": IMPROVISED + " -- derived from document:harbourline_contract.pdf Clause 14.3",
    },
    {
        "id": "performance_security_amount",
        "label": "Performance security as a percentage of the Accepted Contract Amount",
        "source": IMPROVISED + " -- derived from document:harbourline_contract.pdf Clause 4.2",
    },
    {
        "id": "certified_amount",
        "label": "Net certified amount after retention",
        "source": IMPROVISED + " -- arithmetic identity applied to Clause 14.3",
    },
)


def delay_damages(
    accepted_contract_amount: float,
    daily_rate_pct: float,
    delay_days: int,
    cap_pct: float,
) -> Dict[str, Any]:
    """Delay damages: daily percentage of the amount, capped at a percentage.

    Improvised, no Store coverage: the kernel's late-fee identity uses an
    annual rate over a day-count convention; this contract states a daily
    percentage with a hard cap, so the two are not interchangeable. The rate
    and cap are contract terms passed in, never constants in this module.
    """
    uncapped = safe_eval(
        "accepted_contract_amount * daily_rate_pct / 100 * delay_days",
        {
            "accepted_contract_amount": float(accepted_contract_amount or 0.0),
            "daily_rate_pct": float(daily_rate_pct or 0.0),
            "delay_days": float(delay_days or 0),
        },
    )
    cap = safe_eval(
        "accepted_contract_amount * cap_pct / 100",
        {
            "accepted_contract_amount": float(accepted_contract_amount or 0.0),
            "cap_pct": float(cap_pct or 0.0),
        },
    )
    damages = min(float(uncapped), float(cap))
    return {
        "uncapped": round(float(uncapped), 2),
        "cap": round(float(cap), 2),
        "damages": round(damages, 2),
        "cap_reached": bool(cap > 0 and uncapped >= cap),
        "formula": "delay_damages_capped",
        "authority": IMPROVISED,
    }


def retention_amount(gross_amount: float, retention_pct: float) -> float:
    """Retention withheld from a certificate: gross x percentage.

    Improvised, no Store coverage: Clause 14.3 states the percentage, and the
    arithmetic is the contract's own. The percentage is an input.
    """
    value = safe_eval(
        "gross_amount * retention_pct / 100",
        {
            "gross_amount": float(gross_amount or 0.0),
            "retention_pct": float(retention_pct or 0.0),
        },
    )
    return round(float(value), 2)


def performance_security_amount(accepted_contract_amount: float, security_pct: float) -> float:
    """Performance security: percentage of the Accepted Contract Amount.

    Improvised, no Store coverage: Clause 4.2 states the percentage, and the
    arithmetic is the contract's own. The percentage is an input.
    """
    value = safe_eval(
        "accepted_contract_amount * security_pct / 100",
        {
            "accepted_contract_amount": float(accepted_contract_amount or 0.0),
            "security_pct": float(security_pct or 0.0),
        },
    )
    return round(float(value), 2)


def certified_amount(gross_amount: float, retention: float) -> float:
    """Net certified amount: gross less retention.

    Improvised, no Store coverage: arithmetic identity applied to Clause 14.3.
    """
    value = safe_eval(
        "gross_amount - retention",
        {
            "gross_amount": float(gross_amount or 0.0),
            "retention": float(retention or 0.0),
        },
    )
    return round(float(value), 2)
