"""Formula surface: the contract arithmetic the capabilities apply.

Each figure is a function of inputs the caller supplies and a rate the
operator owns (PLATFORM_RATE_* with the contract clause as its default
documented in README). No currency or tax rate is typed in here.
"""

from __future__ import annotations

import os
from typing import Dict, List

RETENTION_PCT = "PLATFORM_RATE_RETENTION_PCT"
DELAY_DAMAGES_PCT_PER_DAY = "PLATFORM_RATE_DELAY_DAMAGES_PCT_PER_DAY"
DELAY_DAMAGES_CAP_PCT = "PLATFORM_RATE_DELAY_DAMAGES_CAP_PCT"
PERFORMANCE_SECURITY_PCT = "PLATFORM_RATE_PERFORMANCE_SECURITY_PCT"


def _setting(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    return float(raw) if raw else float(default)


def _money(value: float) -> float:
    return round(float(value), 2)


def retention_amount(gross: float, pct: float = 5.0) -> float:
    """Clause 14.3: retention held from each Interim Payment Certificate."""
    return _money(float(gross) * float(pct) / 100.0)


def net_after_retention(gross: float, pct: float = 5.0) -> float:
    return _money(float(gross) - retention_amount(gross, pct))


def release_split(retention: float) -> Dict[str, float]:
    """Clause 14.3: 50% at Taking-Over, 50% at the end of the DNP."""
    half = _money(float(retention) * 0.5)
    return {"at_taking_over": half, "at_dnp_end": _money(float(retention) - half)}


def delay_damages(accepted_contract_amount: float, delay_days: int,
                  daily_pct: float = 0.1, cap_pct: float = 10.0) -> Dict[str, float]:
    """Clause 8.7: 0.1% of the Accepted Contract Amount per day, capped 10%."""
    daily = _money(float(accepted_contract_amount) * float(daily_pct) / 100.0)
    accrued = _money(daily * max(0, int(delay_days)))
    cap = _money(float(accepted_contract_amount) * float(cap_pct) / 100.0)
    return {
        "daily_amount": daily,
        "accrued": accrued,
        "cap_amount": cap,
        "payable": min(accrued, cap),
        "cap_reached": accrued >= cap,
        "cap_day": int(cap / daily) if daily > 0 else 0,
    }


def performance_security(accepted_contract_amount: float, pct: float = 10.0) -> float:
    """Clause 4.2: performance security at 10% of the Accepted Contract Amount."""
    return _money(float(accepted_contract_amount) * float(pct) / 100.0)


def retention_pct() -> float:
    return _setting(RETENTION_PCT, 5.0)


def delay_daily_pct() -> float:
    return _setting(DELAY_DAMAGES_PCT_PER_DAY, 0.1)


def delay_cap_pct() -> float:
    return _setting(DELAY_DAMAGES_CAP_PCT, 10.0)


def security_pct() -> float:
    return _setting(PERFORMANCE_SECURITY_PCT, 10.0)


def rate_names() -> List[str]:
    return [RETENTION_PCT, DELAY_DAMAGES_PCT_PER_DAY, DELAY_DAMAGES_CAP_PCT,
            PERFORMANCE_SECURITY_PCT]
