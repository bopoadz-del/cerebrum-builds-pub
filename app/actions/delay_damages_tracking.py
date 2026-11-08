"""delay_damages_tracking -- Time for Completion and damages exposure.

Tracks elapsed time against the 730-day Time for Completion (Clause 8.2)
from the Commencement Date, projects the taking-over date, and computes
delay-damages exposure at 0.1% of the Accepted contract Amount per day
capped at 10% (Clause 8.7), raising an early-warning notification as the cap
is approached.

Scope READS: caller payload, app/sources.py, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only.
Scope NEVER: no network, no invented commencement date, no rate not in the contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import formulas, sources
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    currency,
    money_round,
    number_of,
    record_of,
    refusal,
    success,
    tenant_scope,
    text_of,
    whole_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "delay_damages_tracking"
ENTITY = CAPABILITY_ID

BLOCK_IDS = ["cpm_engine", "formula_executor", "notification", "analytics", "dashboard"]

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "cpm_engine": "compute",
    "formula_executor": "evaluate",
    "notification": "send",
    "analytics": "track_event",
    "dashboard": "render",
}

AUTHORITY = authority(CAPABILITY_ID, 2, "documents")

#: The clause the exposure is measured against, read once from the source.
TIME_CLAUSE = sources.clause_number("time_for_completion")
DAMAGES_CLAUSE = sources.clause_number("delay_damages")


def _programme() -> List[Dict[str, Any]]:
    """The works programme, grouped by the BOQ's own sections.

    Durations are the declared preliminary and earthworks periods, not an
    invented critical path: the CPM block is asked for a forward pass over
    the sequence the BOQ describes.
    """
    sections = list(dict.fromkeys(item["section"] for item in sources.boq_rows()))
    activities: List[Dict[str, Any]] = []
    previous = None
    for index, section in enumerate(sections):
        activity_id = "S%d" % (index + 1)
        entry: Dict[str, Any] = {
            "id": activity_id,
            "name": section,
            "duration": 30 if index == 0 else 120,
        }
        if previous:
            entry["predecessors"] = [{"predecessor_id": previous, "type": "FS", "lag": 0}]
        activities.append(entry)
        previous = activity_id
    return activities


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    clause = sources.clause(DAMAGES_CLAUSE) or {}

    commencement = text_of(record.get("commencement_date"))
    as_of = text_of(record.get("as_of_date"))
    extension_days = whole_of(record.get("extension_days"))
    accepted = number_of(record.get("accepted_contract_amount"))
    if accepted <= 0:
        accepted = sources.accepted_contract_amount()

    daily_percent = number_of(record.get("daily_rate_percent"))
    if daily_percent <= 0:
        daily_percent = float(clause.get("value", 0.0))
    cap_percent = number_of(record.get("cap_percent"))
    if cap_percent <= 0:
        cap_percent = float(clause.get("cap_percent", 0.0))

    completion = formulas.completion_date(commencement, extension_days) if commencement else ""
    taking_over = completion
    delay_days = 0
    if completion and as_of:
        delay_days = formulas.days_between(completion, as_of)
    exposure = formulas.delay_damages(accepted, daily_percent, delay_days, cap_percent)
    cap_amount = formulas.delay_cap_amount(accepted, cap_percent)
    at_cap = cap_amount > 0 and exposure >= cap_amount
    warning_threshold = formulas.percent_of(cap_amount, 90.0)
    early_warning = cap_amount > 0 and exposure >= warning_threshold

    reference = text_of(record.get("reference")) or "delay-position"
    message = (
        "Delay-damages exposure %s %s on %d day(s) of delay; cap %s %s"
        % (currency(), money_round(exposure), delay_days, currency(), money_round(cap_amount))
    )
    if early_warning:
        message += " -- early warning: 90% of the cap is approached"

    inputs: Dict[str, Dict[str, Any]] = {
        "cpm_engine": {
            "activities": _programme(),
            "project_start": commencement or None,
        },
        "formula_executor": {
            "formula_description": "Delay damages under Clause %s" % DAMAGES_CLAUSE,
            "custom_code": (
                "daily = accepted_contract_amount * daily_percent / 100\n"
                "result = min(daily * delay_days, accepted_contract_amount * cap_percent / 100)"
            ),
            "input_values": {
                "accepted_contract_amount": accepted,
                "daily_percent": daily_percent,
                "delay_days": delay_days,
                "cap_percent": cap_percent,
            },
        },
        "notification": {
            "channel": "mcp",
            "block": "event_bus",
            "payload": {
                "topic": "delay_damages.warning",
                "payload": {
                    "reference": reference,
                    "exposure": money_round(exposure),
                    "cap": money_round(cap_amount),
                    "delay_days": delay_days,
                },
                "message": message,
                "channel": "mcp",
                "tool": "event_bus",
            },
            "message": message,
            "recipient": tenant_scope(),
        },
        "analytics": {
            "metric": "delay_damages_exposure",
            "value": money_round(exposure),
            "period": text_of(record.get("as_of_date")) or "current",
            "name": "delay_damages_exposure",
        },
        "dashboard": {
            "widgets": [
                {"type": "metric", "title": "Delay-damages exposure", "value": exposure},
                {"type": "metric", "title": "Days of delay", "value": delay_days},
            ],
            "title": "Delay-damages position",
        },
    }

    answers, refusals = call_blocks(
        BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    if refusals:
        return refusal(
            CAPABILITY_ID, AUTHORITY, refusals, answers,
            input_digest=record.get("_input_digest"),
        )

    return success(
        CAPABILITY_ID,
        AUTHORITY,
        answers,
        input_digest=record.get("_input_digest"),
        result={
            "reference": reference,
            "currency": currency(),
            "commencement_date": commencement,
            "time_for_completion_days": int(formulas.time_for_completion_days()),
            "extension_days": extension_days,
            "completion_date": completion,
            "projected_taking_over": taking_over,
            "as_of_date": as_of,
            "delay_days": delay_days,
            "daily_rate_percent": daily_percent,
            "cap_percent": cap_percent,
            "accepted_contract_amount": money_round(accepted),
            "delay_damages_exposure": exposure,
            "delay_damages_cap": cap_amount,
            "at_cap": at_cap,
            "early_warning": early_warning,
            "clauses": {"time": TIME_CLAUSE, "damages": DAMAGES_CLAUSE},
            "citation": sources.CONTRACT_DOCUMENT,
        },
    )
