"""Formulas used by the contract capabilities.

Kernel definitions are evaluated through the kernel's own safe evaluator:
``universal:late_fee_simple_v1`` for the time-scaled money amount and
``universal:proration_v1`` for a pro-rated release. The capped delay-damages
composition is local, cited to Clause 8.7, and recorded in
app/formulas/writer_definitions.jsonl.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from app.cerebrum_product_kernel.formulas.evaluator import safe_eval

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "docs" / "source_of_record.json"
DEFINITIONS_PATH = ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"

_LATE_FEE_KEY = "universal:late_fee_simple_v1"
_PRORATION_KEY = "universal:proration_v1"


def _definitions() -> dict:
    data = json.loads(DEFINITIONS_PATH.read_text(encoding="utf-8"))
    return {item["key"]: item for item in data.get("definitions", [])}


def _evaluate(key: str, variables: dict) -> float:
    definition = _definitions().get(key)
    if definition is None:
        raise KeyError(key)
    return float(safe_eval(definition["expression"], variables))


def source_of_record() -> dict:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def currency() -> str:
    declared = str(source_of_record().get("currency") or "").strip()
    if declared:
        return declared
    from app import money_settings

    return money_settings.currency()


def contract_clause(clause_id: str) -> dict:
    for document in source_of_record().get("documents", []):
        for clause in document.get("clauses", []):
            if str(clause.get("id")) == str(clause_id):
                return {**clause, "document": "document:" + str(document.get("filename"))}
    raise KeyError("no clause " + str(clause_id))


def clause_ratio(clause_id: str) -> float:
    return float(contract_clause(clause_id).get("value") or 0.0)


def boq_items() -> list:
    for document in source_of_record().get("documents", []):
        if document.get("kind") == "boq":
            return list(document.get("items") or [])
    return []


def boq_index() -> dict:
    return {str(item.get("item")): item for item in boq_items()}


def boq_total() -> float:
    return round(sum(float(i["qty"]) * float(i["rate"]) for i in boq_items()), 2)


def item_value(code: str) -> float:
    item = boq_index().get(str(code))
    if item is None:
        return 0.0
    return round(float(item["qty"]) * float(item["rate"]), 2)


def money(value) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def retention_amount(certified_amount: float) -> float:
    rate = clause_ratio("14.3")
    return money(float(certified_amount or 0.0) * rate)


def retention_at_taking_over(certified_amount: float) -> float:
    return money(retention_amount(certified_amount) * float(contract_clause("14.3").get("release_at_taking_over") or 0.0))


def performance_security(accepted_contract_amount: float) -> float:
    return money(float(accepted_contract_amount or 0.0) * clause_ratio("4.2"))


def delay_damages(accepted_contract_amount: float, days_of_delay: int) -> dict:
    """Clause 8.7: 0.1% per day, capped at 10% of the Accepted Contract Amount."""
    clause = contract_clause("8.7")
    daily_rate = float(clause["value"])
    cap_ratio = float(clause.get("cap_ratio") or 0.0)
    amount = float(accepted_contract_amount or 0.0)
    days = max(0, int(days_of_delay or 0))
    uncapped = _evaluate(
        _LATE_FEE_KEY,
        {
            "overdue_amount": amount,
            "annual_rate": daily_rate * 365.0,
            "days_overdue": days,
            "days_in_year": 365.0,
        },
    )
    cap = money(amount * cap_ratio)
    assessed = money(min(uncapped, cap))
    return {
        "accepted_contract_amount": money(amount),
        "days_of_delay": days,
        "daily_rate": daily_rate,
        "cap_ratio": cap_ratio,
        "uncapped_amount": money(uncapped),
        "cap_amount": cap,
        "damages_amount": assessed,
        "capped": uncapped > cap,
        "clause": "8.7",
        "source": clause["document"],
    }


def pro_rate(amount: float, days_used: int, days_in_period: int) -> float:
    return money(
        _evaluate(
            _PRORATION_KEY,
            {
                "amount": float(amount or 0.0),
                "days_used": max(0, int(days_used or 0)),
                "days_in_period": max(1, int(days_in_period or 1)),
            },
        )
    )


def delay_damages_code() -> str:
    """The custom formula handed to formula_executor, kept as one definition."""
    return (
        "base = accepted_contract_amount * daily_rate * days_of_delay\n"
        "cap = accepted_contract_amount * cap_ratio\n"
        "result = round(min(base, cap), 2)\n"
    )


def finite_number(value, default=0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default
