"""Delay damages under Clause 8.7, with the Clause 8.2 completion date."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app import contract_terms, formulas
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["cpm_engine", "formula_executor", "finance_planning", "audit"]


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    days = int(record.get("delay_days") or 0)
    contract_amount = float(record.get("accepted_contract_amount") or 0.0)
    daily_rate = float(record.get("delay_damages_rate") or contract_terms.delay_damages_daily_rate())
    cap_ratio = float(record.get("damages_cap_ratio") or contract_terms.delay_damages_cap_ratio())
    daily_rate = min(max(daily_rate, 0.0), 1.0)
    cap_ratio = min(max(cap_ratio, 0.0), 1.0)

    accrued = formulas.delay_damages(contract_amount, daily_rate, days)
    cap = formulas.rate_applied(contract_amount, cap_ratio)
    accrued_value = round(float(accrued["value"]), 2)
    cap_value = round(float(cap["value"]), 2)
    assessed = round(min(accrued_value, cap_value), 2)
    capped = accrued_value > cap_value

    completion = ""
    completion_error = ""
    start = str(record.get("commencement_date") or "").strip()
    if start:
        try:
            completion = contract_terms.completion_date(start)
        except ValueError as exc:
            completion_error = "commencement_date is not an ISO date: %s" % exc

    blocks: Dict[str, Any] = {}

    schedule, error = call("cpm_engine", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    schedule_body = schedule.get("result") if isinstance(schedule.get("result"), dict) else schedule
    blocks["cpm_engine"] = {
        "project_duration": (schedule_body or {}).get("project_duration"),
        "critical_path": (schedule_body or {}).get("critical_path") or [],
    }

    working = dict(record)
    working["damages_assessed"] = assessed
    evaluated, error = call("formula_executor", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["formula_executor"] = {
        "value": evaluated.get("execution_result"),
        "address": accrued["address"],
    }

    provision, error = call("finance_planning", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    budget = provision.get("budget") if isinstance(provision.get("budget"), dict) else {}
    blocks["finance_planning"] = {"budget_id": budget.get("id"), "amount": budget.get("amount")}

    logged, error = call("audit", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["audit"] = {"entry_id": (logged.get("entry") or {}).get("id")}

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "commencement_date": start,
        "delay_days": days,
        "accepted_contract_amount": contract_amount,
        "delay_damages_rate": daily_rate,
        "damages_cap_ratio": cap_ratio,
        "damages_assessed": assessed,
    }
    computed = {
        "completion_date": completion,
        "completion_clause": "8.2",
        "completion_error": completion_error or None,
        "accrued_damages": accrued_value,
        "damages_cap": cap_value,
        "damages_assessed": assessed,
        "capped": capped,
        "daily_rate": daily_rate,
        "damages_formula": accrued["address"],
        "cap_formula": cap["address"],
        "provision_budget_id": budget.get("id"),
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("formulas"),
    }
