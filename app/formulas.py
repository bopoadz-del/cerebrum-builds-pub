"""The contract arithmetic, in one place, derived from the uploaded clause text.

Every figure is read from app.sources (the cited document) or supplied by the
caller; no rate, cap or currency is typed into this module.

Scope READS: caller values and app.sources.
Scope WRITES: nothing.
Scope NEVER: no network, no invented contract term.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app import sources


def money(value: Any) -> float:
    try:
        if isinstance(value, bool) or value in (None, ""):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def number(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool) or value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def boq_line_value(quantity: Any, rate: Any) -> float:
    """A measured BOQ line value: quantity x rate, to two decimals."""
    return money(number(quantity) * number(rate))


def retention_amount(gross: Any, percent: Any) -> float:
    """Retention withheld on an Interim Payment Certificate (Clause 14.3)."""
    return money(number(gross) * number(percent) / 100.0)


def retention_release(retention: Any, share_percent: Any) -> float:
    """The part of the retention released at a milestone."""
    return money(number(retention) * number(share_percent) / 100.0)


def net_payable(gross: Any, retention: Any, released: Any = 0.0) -> float:
    return money(number(gross) - number(retention) + number(released))


def delay_damages(accepted_amount: Any, daily_percent: Any, delay_days: Any,
                  cap_percent: Any) -> float:
    """Delay damages: daily % of the accepted contract amount, capped."""
    daily = money(number(accepted_amount) * number(daily_percent) / 100.0)
    uncapped = daily * max(0.0, number(delay_days))
    cap = number(accepted_amount) * number(cap_percent) / 100.0
    return money(min(uncapped, cap))


def delay_cap_amount(accepted_amount: Any, cap_percent: Any) -> float:
    return money(number(accepted_amount) * number(cap_percent) / 100.0)


def time_for_completion_days() -> float:
    return sources.clause_value("time_for_completion")


def defects_notification_days() -> float:
    return sources.clause_value("defects_notification")


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def days_between(start: Any, end: Any) -> int:
    first, last = parse_date(start), parse_date(end)
    if first is None or last is None:
        return 0
    return max(0, (last - first).days)


def add_days(start: Any, days: int) -> str:
    first = parse_date(start)
    if first is None:
        return ""
    return (first + timedelta(days=int(days))).isoformat()


def completion_date(commencement: Any, extension_days: Any = 0) -> str:
    return add_days(
        commencement, int(time_for_completion_days()) + int(number(extension_days))
    )


def taking_over_date(commencement: Any, extension_days: Any = 0) -> str:
    return completion_date(commencement, extension_days)


def defects_period_end(taking_over: Any) -> str:
    return add_days(taking_over, int(defects_notification_days()))


def performance_security(accepted_amount: Any) -> float:
    return money(number(accepted_amount) * sources.clause_value("performance_security") / 100.0)


def percent_of(value: Any, percent: Any) -> float:
    return money(number(value) * number(percent) / 100.0)


def round_money(value: Any) -> float:
    return money(value)
