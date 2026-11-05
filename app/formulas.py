"""Contract arithmetic as functions -- the clause figures live in one place.

Every capability that certifies money or time calls these, so the retention,
performance-security and delay-damages rules cannot drift between handlers.
The constants come from the uploaded contract excerpt (``app/contract_data.py``).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from app import contract_data


def round_money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def retention_amount(gross: float, pct: float = contract_data.RETENTION_PCT) -> float:
    """Clause 14.3: 5% of each Interim Payment Certificate."""
    return round_money(max(0.0, float(gross)) * float(pct) / 100.0)


def retention_release(retention: float) -> Dict[str, float]:
    """Clause 14.3: 50% at Taking-Over and 50% at the end of the DNP."""
    held = max(0.0, float(retention))
    return {
        "at_taking_over": round_money(held * contract_data.RETENTION_RELEASE_AT_TAKING_OVER / 100.0),
        "at_dnp_end": round_money(held * contract_data.RETENTION_RELEASE_AT_DNP_END / 100.0),
    }


def performance_security(
    accepted_contract_amount: float,
    pct: float = contract_data.PERFORMANCE_SECURITY_RATE_PCT,
    applies: bool = True,
) -> float:
    """Clause 4.2: 10% of the Accepted Contract Amount (on the first certificate)."""
    if not applies:
        return 0.0
    return round_money(max(0.0, float(accepted_contract_amount)) * float(pct) / 100.0)


def net_after_deductions(gross: float, retention: float, performance: float) -> float:
    return round_money(max(0.0, float(gross) - float(retention) - float(performance)))


def planned_completion(commencement: date, days: int = contract_data.TIME_FOR_COMPLETION_DAYS) -> date:
    """Clause 8.2: Time for Completion is 730 days from the Commencement Date."""
    return commencement + timedelta(days=int(days))


def delay_days(planned: date, assessed: date) -> int:
    return max(0, (assessed - planned).days)


def delay_damages(
    accepted_contract_amount: float,
    days: int,
    rate_pct: float = contract_data.DELAY_DAMAGES_RATE_PCT,
    cap_pct: float = contract_data.DELAY_DAMAGES_CAP_PCT,
) -> Dict[str, Any]:
    """Clause 8.7: 0.1%/day of the Accepted Contract Amount, capped at 10%."""
    amount = max(0.0, float(accepted_contract_amount))
    uncapped = amount * float(rate_pct) / 100.0 * int(days)
    cap = amount * float(cap_pct) / 100.0
    damages = round_money(min(uncapped, cap))
    return {
        "delay_days": int(days),
        "uncapped": round_money(uncapped),
        "cap": round_money(cap),
        "delay_damages": damages,
        "cap_reached": bool(days and uncapped >= cap),
    }


def defects_notification_end(taking_over: date) -> date:
    """Clause 11.1: 365 days from Taking-Over."""
    return taking_over + timedelta(days=contract_data.DEFECTS_NOTIFICATION_DAYS)
