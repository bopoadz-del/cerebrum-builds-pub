"""delay_damages_tracking — Time for Completion against the contract.

Clause 8.2 of document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf
sets Time for Completion at 730 days; Clause 8.7 sets delay damages at 0.1% of
the Accepted Contract Amount per day, capped at 10%. The days, the rate and
the cap are operator settings (app.contract.term), never constants here.

READS:  the capability payload, the contract excerpt, block answers.
WRITES: the assessment record returned to the route (the route persists it).
NEVER:  stores a record itself, or reports damages over a block that failed.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

from app import contract, dispatch, formulas, models
from app.actions._common import (
    BlockRefused,
    as_date,
    as_float,
    as_int,
    call,
    envelope,
    refusal,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["formula_executor", "cpm_engine", "validation"]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_CONTRACT = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"

#: A hundred years of delay is already absurd; anything beyond is refused at
#: the edge (CONSTRAINTS.max) and clamped here so no schedule loop can run away.
MAX_DELAY_DAYS = 36500


def _delay_days(data: Dict[str, Any], commencement: _dt.date | None, completion: _dt.date | None) -> int:
    stated = as_int(data.get("days_of_delay"), -1)
    if stated >= 0:
        return min(stated, MAX_DELAY_DAYS)
    if commencement is None or completion is None:
        return 0
    limit = contract.term_int("time_for_completion_days")
    deadline = commencement + _dt.timedelta(days=limit)
    return min(max((completion - deadline).days, 0), MAX_DELAY_DAYS)


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.DelayDamagesAssessment.from_dict(data)
    record = model.to_dict()

    commencement = as_date(data.get("commencement_date"))
    completion = as_date(data.get("completion_date"))
    days = _delay_days(data, commencement, completion)
    aca = as_float(data.get("accepted_contract_amount"), 0.0) or float(contract.boq_total())
    limit_days = contract.term_int("time_for_completion_days")
    daily_rate = float(contract.term("delay_damages_daily_rate"))
    cap_rate = float(contract.term("delay_damages_cap_rate"))

    damages = formulas.evaluate(
        "delay_damages_capped",
        accepted_contract_amount=aca,
        days_of_delay=days,
        daily_rate=daily_rate,
        cap_rate=cap_rate,
    )

    deadline = None
    if commencement is not None:
        deadline = formulas.evaluate(
            "time_for_completion_deadline",
            commencement_date=commencement.isoformat(),
            time_for_completion_days=limit_days,
        )

    code = (
        "result = min(accepted_contract_amount * daily_rate * days_of_delay, "
        "accepted_contract_amount * cap_rate)"
    )
    try:
        executed = call(
            "formula_executor",
            {
                "formula_description": "delay damages under clause 8.7, capped at 10%",
                "input_values": {
                    "accepted_contract_amount": aca,
                    "daily_rate": daily_rate,
                    "days_of_delay": days,
                    "cap_rate": cap_rate,
                },
                "custom_code": code,
            },
            action=None,
        )
        schedule = call(
            "cpm_engine",
            {
                "activities": [
                    {"id": "commencement", "name": "Commencement Date", "duration": 0, "predecessors": []},
                    {
                        "id": "works",
                        "name": "Works under clause 8.2",
                        "duration": limit_days,
                        "predecessors": ["commencement"],
                    },
                    {
                        "id": "delay",
                        "name": "Days of delay under clause 8.7",
                        "duration": days,
                        "predecessors": ["works"],
                    },
                ],
                "project_start": (commencement or _dt.date.today()).isoformat(),
            },
            action="compute",
        )
        checked = call(
            "validation",
            {
                "item": {
                    "id": str(data.get("assessment_number") or data.get("reference") or "assessment"),
                    "type": "delay_damages_assessment",
                    "value": float(damages["amount"]),
                    "duration_days": days,
                }
            },
            action="validate_pipeline",
        )
    except BlockRefused as exc:
        return refusal(exc.message)

    pipeline = str(checked.get("status") or "")
    if pipeline not in {"ok", "warn", "skipped"}:
        return refusal(f"validation refused the assessment: {pipeline}")

    result = {
        "assessment": {
            "days_of_delay": days,
            "time_for_completion_days": limit_days,
            "time_for_completion_deadline": deadline,
            "accepted_contract_amount": aca,
            "daily_rate": daily_rate,
            "cap_rate": cap_rate,
            "delay_damages": damages["amount"],
            "uncapped_damages": damages["uncapped_amount"],
            "cap_amount": damages["cap_amount"],
            "capped": damages["capped"],
            "notice_served": bool(data.get("notice_served")),
            "contract_clause": "8.7",
        },
        "formula": {
            "executed": executed.get("execution_result"),
            "generated_code": executed.get("generated_code"),
        },
        "schedule": {
            "project_duration": schedule.get("project_duration"),
            "project_finish": schedule.get("project_finish"),
            "critical_path": schedule.get("critical_path"),
        },
        "validation": {
            "status": pipeline,
            "stages": [stage.get("stage") for stage in checked.get("stages") or []],
        },
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": _CONTRACT,
        },
    }
    record["days_of_delay"] = days
    record["accepted_contract_amount"] = aca
    record["commencement_date"] = commencement.isoformat() if commencement else record.get("commencement_date")
    record["completion_date"] = completion.isoformat() if completion else record.get("completion_date")
    if not record.get("assessment_note"):
        record["assessment_note"] = (
            f"{days} day(s) of delay; damages {damages['amount']} under clause 8.7"
        )
    return envelope(record, result)
