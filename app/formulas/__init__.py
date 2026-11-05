"""The formulas this platform computes, and where each one comes from.

Resolution order: the Cerebrum kernel's universal definitions first, the
Store pack second, and only then a formula written here. Every definition
below is contract arithmetic that the kernel does not carry (a delay-damages
cap, a retention release share); each one is labelled "improvised, no Store
coverage" with the clause it comes from, and is registered in
writer_definitions.jsonl and new_domain_candidates.jsonl beside this module.

A figure the customer owns (0.1% per day, the 10% cap, the 5% retention) is
never a constant here: it is read from app.contract.term(), which the
operator sets.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Dict, List

from app import contract

ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS_PATH = Path(__file__).resolve().parent / "writer_definitions.jsonl"
CANDIDATES_PATH = ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "new_domain_candidates.jsonl"

MONEY_QUANTUM = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


#: id -> definition row. ``source`` says where the arithmetic comes from.
DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "certificate_gross_amount": {
        "label": "Interim Payment Certificate gross value: measured quantity x BOQ rate",
        "source": "improvised, no Store coverage; priced BOQ item rates from "
        "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx",
        "inputs": ["measured_quantity", "unit_rate"],
    },
    "retention_amount": {
        "label": "Retention held from an Interim Payment Certificate",
        "source": "improvised, no Store coverage; Clause 14.3 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["certified_amount", "retention_rate"],
    },
    "certificate_net_payable": {
        "label": "Net payable on a certificate after retention",
        "source": "improvised, no Store coverage; Clause 14.3 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["gross_amount", "retention_amount"],
    },
    "performance_security_amount": {
        "label": "Performance security obligation",
        "source": "improvised, no Store coverage; Clause 4.2 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["accepted_contract_amount", "performance_security_rate"],
    },
    "delay_damages_capped": {
        "label": "Delay damages: daily rate x days of delay, capped",
        "source": "improvised, no Store coverage; Clause 8.7 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": [
            "accepted_contract_amount",
            "daily_rate",
            "days_of_delay",
            "cap_rate",
        ],
    },
    "time_for_completion_deadline": {
        "label": "Time for Completion deadline: commencement date + contract days",
        "source": "improvised, no Store coverage; Clause 8.2 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["commencement_date", "time_for_completion_days"],
    },
    "defects_notification_end": {
        "label": "End of the Defects Notification Period: Taking-Over + 365 days",
        "source": "improvised, no Store coverage; Clause 11.1 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["taking_over_date", "defects_notification_days"],
    },
    "retention_release_share": {
        "label": "Retention released at a release stage",
        "source": "improvised, no Store coverage; Clause 14.3 of "
        "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        "inputs": ["retention_held", "share", "already_released"],
    },
}


def _gross(measured_quantity: Any, unit_rate: Any) -> Decimal:
    return money(_d(measured_quantity) * _d(unit_rate))


def _retention(certified_amount: Any, retention_rate: Any = None) -> Decimal:
    rate = _d(retention_rate) if retention_rate is not None else contract.term("retention_rate")
    return money(_d(certified_amount) * rate)


def _net(gross_amount: Any, retention_amount: Any) -> Decimal:
    return money(_d(gross_amount) - _d(retention_amount))


def _performance_security(accepted_contract_amount: Any, rate: Any = None) -> Decimal:
    return money(
        _d(accepted_contract_amount)
        * (_d(rate) if rate is not None else contract.term("performance_security_rate"))
    )


def _delay_damages(
    accepted_contract_amount: Any,
    days_of_delay: Any,
    daily_rate: Any = None,
    cap_rate: Any = None,
) -> Dict[str, Any]:
    aca = _d(accepted_contract_amount)
    days = max(0, int(_d(days_of_delay)))
    rate = _d(daily_rate) if daily_rate is not None else contract.term("delay_damages_daily_rate")
    cap = _d(cap_rate) if cap_rate is not None else contract.term("delay_damages_cap_rate")
    uncapped = aca * rate * days
    ceiling = aca * cap
    amount = min(uncapped, ceiling)
    return {
        "amount": str(money(amount)),
        "uncapped_amount": str(money(uncapped)),
        "cap_amount": str(money(ceiling)),
        "capped": uncapped > ceiling,
        "days_of_delay": days,
        "daily_rate": str(rate),
        "cap_rate": str(cap),
    }


def _deadline(commencement_date: Any, time_for_completion_days: Any = None) -> str:
    import datetime as _dt

    start = _dt.date.fromisoformat(str(commencement_date)[:10])
    limit = (
        int(_d(time_for_completion_days))
        if time_for_completion_days is not None
        else contract.term_int("time_for_completion_days")
    )
    return (start + _dt.timedelta(days=limit)).isoformat()


def _defects_end(taking_over_date: Any, defects_notification_days: Any = None) -> str:
    import datetime as _dt

    start = _dt.date.fromisoformat(str(taking_over_date)[:10])
    limit = (
        int(_d(defects_notification_days))
        if defects_notification_days is not None
        else contract.term_int("defects_notification_days")
    )
    return (start + _dt.timedelta(days=limit)).isoformat()


def _release_share(retention_held: Any, share: Any, already_released: Any = 0) -> Dict[str, Any]:
    held = _d(retention_held)
    fraction = _d(share)
    released = _d(already_released)
    amount = min(held - released, held * fraction)
    return {
        "amount": str(money(max(amount, Decimal("0")))),
        "remaining": str(money(max(held - released - amount, Decimal("0")))),
        "share": str(fraction),
    }


EVALUATORS: Dict[str, Callable[..., Any]] = {
    "certificate_gross_amount": _gross,
    "retention_amount": _retention,
    "certificate_net_payable": _net,
    "performance_security_amount": _performance_security,
    "delay_damages_capped": _delay_damages,
    "time_for_completion_deadline": _deadline,
    "defects_notification_end": _defects_end,
    "retention_release_share": _release_share,
}


def evaluate(name: str, **inputs: Any) -> Any:
    """Evaluate one named formula with the caller's own inputs."""
    if name not in EVALUATORS:
        raise KeyError(f"unknown formula: {name}")
    return EVALUATORS[name](**inputs)


def catalogue() -> List[Dict[str, Any]]:
    return [{"id": key, **value} for key, value in sorted(DEFINITIONS.items())]


def writer_definitions() -> List[Dict[str, str]]:
    path = DEFINITIONS_PATH
    if not path.is_file():
        return []
    rows: List[Dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


# -------- kernel formulas used by the platform, by address ----------------
KERNEL_ADDRESSES = {
    "proration": "universal:proration_v1",
    "late_fee_simple": "universal:late_fee_simple_v1",
    "tax_amount": "universal:tax_amount_v1",
    "simple_interest": "universal:simple_interest_v1",
}


def kernel_definition(address: str) -> Dict[str, Any]:
    path = ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("definitions") if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = list(rows.values())
    for row in rows or []:
        if isinstance(row, dict) and row.get("key") == address:
            return row
    raise KeyError(f"kernel definition not found: {address}")
