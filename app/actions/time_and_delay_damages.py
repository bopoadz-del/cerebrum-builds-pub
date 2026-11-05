"""time_and_delay_damages -- Clauses 8.2 and 8.7, day by day.

Time for Completion is 730 days from the Commencement Date (Clause 8.2).
Delay damages accrue at 0.1% of the Accepted Contract Amount per day of delay,
capped at 10% of the Accepted Contract Amount (Clause 8.7). The exposure is
computed from the dates in the record, not from a caller-supplied total.

READS   the request record, the contract clause values and the uploaded BOQ.
WRITES  a delay assessment under STORAGE_PATH/workspace and this capability's
        result; the ROUTE persists the record, never the handler.
NEVER   reports damages above the 10% cap, or a delay before Time for
        Completion has expired.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any, Dict

from app import contract_data, formulas
from app.actions import _support
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS
from app.actions._support import as_date, ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "time_and_delay_damages"
ENTITY = "time_and_delay_damages"
BLOCK_IDS = ["cpm_engine", "formula_executor", "finance_planning", "notification", "dashboard", "audit"]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    commencement = as_date(record.get("commencement_date"))
    commencement_assumed = commencement is None
    if commencement is None:
        # No commencement on the record: assess from today. Time for Completion
        # has not expired, so the exposure is zero -- never negative, never a
        # guessed start date pulled from the contract's example figures.
        commencement = date.today()
    completion = as_date(record.get("completion_date"))
    planned_completion = formulas.planned_completion(
        commencement,
        _support.int_of(record, "time_for_completion_days", contract_data.TIME_FOR_COMPLETION_DAYS),
    )
    assessment_date = completion or planned_completion
    delay_days = formulas.delay_days(planned_completion, assessment_date)

    accepted = _support.number_of(
        record, "accepted_contract_amount", contract_data.boq_total()
    ) or contract_data.boq_total()
    rate_pct = _support.number_of(
        record, "delay_damages_rate_pct", contract_data.DELAY_DAMAGES_RATE_PCT
    )
    if rate_pct <= 0:
        rate_pct = contract_data.DELAY_DAMAGES_RATE_PCT
    cap_pct = _support.number_of(
        record, "damages_cap_pct", contract_data.DELAY_DAMAGES_CAP_PCT
    )
    if cap_pct <= 0:
        cap_pct = contract_data.DELAY_DAMAGES_CAP_PCT

    exposure = formulas.delay_damages(accepted, delay_days, rate_pct, cap_pct)
    damages = exposure["delay_damages"]
    cap_reached = exposure["cap_reached"]

    workspace = _support.workspace_dir(CAPABILITY_ID)
    assessment = {
        "reference": reference,
        "commencement_date": commencement.isoformat(),
        "time_for_completion_days": _support.int_of(
            record, "time_for_completion_days", contract_data.TIME_FOR_COMPLETION_DAYS
        ),
        "planned_completion": planned_completion.isoformat(),
        "assessment_date": assessment_date.isoformat(),
        "commencement_assumed": commencement_assumed,
        "delay_days": delay_days,
        "accepted_contract_amount": accepted,
        "delay_damages_rate_pct": rate_pct,
        "uncapped_damages": exposure["uncapped"],
        "damages_cap_pct": cap_pct,
        "damages_cap": exposure["cap"],
        "delay_damages": damages,
        "cap_reached": cap_reached,
        "currency": "SAR",
        "clauses": {"time_for_completion": "8.2", "delay_damages": "8.7"},
    }
    assessment_file = workspace / f"delay_{reference.replace('/', '_')}_{uuid.uuid4().hex[:8]}.json"
    assessment_file.write_text(json.dumps(assessment, indent=2, sort_keys=True), encoding="utf-8")

    inputs: Dict[str, Dict[str, Any]] = {
        "cpm_engine": {
            "project_start": commencement.isoformat(),
            "activities": [
                {
                    "id": "time-for-completion",
                    "name": "Time for Completion",
                    "duration": int(assessment["time_for_completion_days"]),
                    "predecessors": [],
                },
                {
                    "id": "delay-exposure",
                    "name": "Assessed delay",
                    "duration": delay_days,
                    "predecessors": [
                        {
                            "predecessor_id": "time-for-completion",
                            "type": "FS",
                            "lag": 0,
                        }
                    ],
                },
            ],
        },
        "formula_executor": {
            "expression": "min(delay_days * accepted_contract_amount * rate_pct / 100, accepted_contract_amount * cap_pct / 100)",
            "variables": {
                "commencement_assumed": commencement_assumed,
        "delay_days": delay_days,
                "accepted_contract_amount": accepted,
                "rate_pct": rate_pct,
                "cap_pct": cap_pct,
            },
        },
        "finance_planning": {
            "tenant_id": _support.text_of(record, "_tenant_id") or "local",
            "name": f"Delay damages exposure {reference}",
            "amount": damages,
            "period": assessment_date.isoformat()[:7],
            "budget_id": f"delay:{reference}",
        },
        "notification": {
            "channel": "mcp",
            "message": f"Delay exposure for {reference}: {delay_days} day(s), SAR {damages}",
            "block": "audit",
            "tool": "audit",
            "topic": "delay_damages.assessed",
            "payload": assessment,
        },
        "dashboard": {
            "title": f"Time and delay damages -- {reference}",
            "metrics": {
                "commencement_assumed": commencement_assumed,
        "delay_days": delay_days,
                "delay_damages": damages,
                "cap_reached": cap_reached,
            },
        },
        "audit": {
            "action_type": "delay_damages_assessed",
            "principal_id": "contract-administrator",
            "payload": assessment,
            "result": {"delay_damages": damages, "reference": reference},
            "reference": reference,
        },
    }

    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result = {
        **assessment,
        "block_evidence": {
            "schedule_computed": isinstance(answers.get("cpm_engine"), dict)
            and answers["cpm_engine"].get("ok") is not False,
            "formula_checked": isinstance(answers.get("formula_executor"), dict)
            and answers["formula_executor"].get("ok") is not False,
            "budget_planned": isinstance(answers.get("finance_planning"), dict)
            and answers["finance_planning"].get("ok") is not False,
            "notice_sent": isinstance(answers.get("notification"), dict)
            and answers["notification"].get("ok") is not False,
        },
        "assessment_file": str(assessment_file),
        "citation": contract_data.CONTRACT_DOCUMENT,
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 3 formulas",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
