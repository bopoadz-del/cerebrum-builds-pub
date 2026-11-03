"""delay_damages_tracking: Clauses 8.2 and 8.7.

Computes the 730-day Time for Completion from the Commencement Date,
accrues delay damages at 0.1% of the Accepted Contract Amount per day,
enforces the 10% cap, and names the day the cap is reached.
"""

from __future__ import annotations

from typing import Any, Dict

from app import contract_data, formulas
from app.action_support import (
    BlockCallFailed,
    as_date,
    as_float,
    as_int,
    answer,
    call_block,
    clause_setting,
    refused,
    round_money,
)
from app.block_inputs import default_block_action

CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["cpm_engine", "formula_executor", "analytics", "dashboard"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    commencement = as_date(record.get("commencement_date"))
    completion = as_date(record.get("completion_date"), commencement)
    time_for_completion = int(clause_setting("PLATFORM_RATE_TIME_FOR_COMPLETION_DAYS", 730))
    daily_pct = formulas.delay_daily_pct()
    cap_pct = formulas.delay_cap_pct()
    aca = contract_data.accepted_contract_amount(as_float(record.get("accepted_contract_amount"), 0.0))

    elapsed = max(0, (completion - commencement).days)
    delay_days = max(0, elapsed - time_for_completion)
    if record.get("delay_days") not in (None, ""):
        delay_days = max(0, as_int(record.get("delay_days"), delay_days))
    computed = formulas.delay_damages(aca, delay_days, daily_pct, cap_pct)
    daily_amount = computed["daily_amount"]
    accrued = computed["accrued"]
    cap_amount = computed["cap_amount"]
    damages = computed["payable"]
    cap_reached = computed["cap_reached"]
    cap_day = computed["cap_day"]

    try:
        schedule = call_block(
            "cpm_engine",
            {
                "activities": [
                    {"id": item["item"], "name": item["description"],
                     "duration": max(1, int(item["qty"]))}
                    for item in contract_data.BOQ_ITEMS
                ],
                "project_start": commencement.isoformat(),
                "data_date": completion.isoformat(),
            },
            action=BLOCK_DEFAULT_ACTIONS.get("cpm_engine"),
        )
        formula = call_block(
            "formula_executor",
            {"formula": "damages = accepted_contract_amount * daily_rate * delay_days",
             "params": {"accepted_contract_amount": aca, "daily_rate": daily_pct / 100.0,
                        "delay_days": delay_days}},
            action=BLOCK_DEFAULT_ACTIONS.get("formula_executor"),
        )
        metric = call_block(
            "analytics",
            {"metric": "delay_damages_accrued", "value": damages,
             "dimensions": {"capability": CAPABILITY_ID, "reference": reference}},
            action=BLOCK_DEFAULT_ACTIONS.get("analytics"),
        )
        board = call_block(
            "dashboard",
            {"widgets": [{"id": "delay_damages", "type": "metric", "value": damages}]},
            action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "time_for_completion_days": time_for_completion,
            "elapsed_days": elapsed,
            "delay_days": delay_days,
            "daily_pct": daily_pct,
            "daily_amount": daily_amount,
            "accrued": accrued,
            "cap_pct": cap_pct,
            "cap_amount": cap_amount,
            "delay_damages": damages,
            "cap_reached": cap_reached,
            "cap_reached_on_day": cap_day,
            "commencement_date": commencement.isoformat(),
            "completion_date": completion.isoformat(),
            "clauses": {"8.2": contract_data.CLAUSES["8.2"], "8.7": contract_data.CLAUSES["8.7"]},
            "schedule_status": (schedule.get("status") if isinstance(schedule, dict) else None),
            "formula_status": (formula.get("status") if isinstance(formula, dict) else None),
            "tracked_metric": (metric.get("metric") if isinstance(metric, dict) else None),
            "dashboard_widgets": len((board.get("widgets") or []) if isinstance(board, dict) else []),
        },
        authority="2:documents",
    )
