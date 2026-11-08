"""delay_damages_tracking -- Time for Completion and Clause 8.7 exposure.

Elapsed time is measured against the contractual Time for Completion (Clause
8.2) plus any extension-of-time days the caller records. Delay damages are the
per-day percentage of the Accepted Contract Amount, capped at the contractual
percentage (Clause 8.7); the assessment names the cap when it is reached and
chains the evidence for an extension-of-time position.

READS   the request record, the contract terms and the BOQ total.
WRITES  the assessment under STORAGE_PATH/workspace; the ROUTE persists the
        assessment, never this handler.
NEVER   invents a commencement date, a day count or a rate: a missing figure
        is stated as an assumption instead.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from app import contract_data, formulas
from app import capability_support as _support
from app.capability_support import as_date, ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["cpm_engine", "formula_executor", "transaction_state_machine", "notification", "evidence_chain"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}


def _schedule_activities(reference: str, delay_days: int, extension_days: int) -> list:
    """A two-activity network carrying the contractual and actual durations."""
    contractual = max(1, int(contract_data.TIME_FOR_COMPLETION_DAYS))
    return [
        {"id": "TFC", "name": "Time for Completion", "duration": contractual, "predecessors": []},
        {
            "id": "EXT",
            "name": "Extension of time",
            "duration": max(0, int(extension_days)),
            "predecessors": [{"predecessor_id": "TFC", "type": "FS", "lag": 0}],
        },
        {
            "id": "DLY",
            "name": f"Delay exposure {reference}",
            "duration": max(0, int(delay_days)),
            "predecessors": [{"predecessor_id": "EXT", "type": "FS", "lag": 0}],
        },
    ]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)

    commencement = as_date(record.get("commencement_date"))
    assessment_date = as_date(record.get("assessment_date")) or date.today()
    extension_days = max(0, _support.int_of(record, "extension_days", 0))

    stated = _support.int_of(record, "delay_days", -1)
    assumption = ""
    if stated >= 0:
        delay_days = stated
        basis = "stated"
    elif commencement is not None:
        elapsed = max(0, (assessment_date - commencement).days)
        allowable = contract_data.TIME_FOR_COMPLETION_DAYS + extension_days
        delay_days = max(0, elapsed - allowable)
        basis = "elapsed-minus-contractual-time"
    else:
        delay_days = 0
        basis = "no-commencement-recorded"
        assumption = (
            "No commencement date on the record; exposure is assessed as zero "
            "rather than assuming a start date the contract does not state."
        )

    accepted = _support.number_of(record, "accepted_contract_amount", 0.0)
    if accepted <= 0:
        accepted = contract_data.boq_total()
    daily_pct = _support.number_of(record, "daily_rate_pct", contract_data.DELAY_DAMAGES_DAILY_PCT)
    if daily_pct <= 0:
        daily_pct = contract_data.DELAY_DAMAGES_DAILY_PCT
    cap_pct = _support.number_of(record, "cap_pct", contract_data.DELAY_DAMAGES_CAP_PCT)
    if cap_pct <= 0:
        cap_pct = contract_data.DELAY_DAMAGES_CAP_PCT

    damages = formulas.delay_damages(accepted, daily_pct, delay_days, cap_pct)
    assessment = {
        "reference": reference,
        "commencement_date": commencement.isoformat() if commencement else None,
        "assessment_date": assessment_date.isoformat(),
        "time_for_completion_days": contract_data.TIME_FOR_COMPLETION_DAYS,
        "extension_days": extension_days,
        "delay_days": delay_days,
        "delay_basis": basis,
        "accepted_contract_amount": accepted,
        "daily_rate_pct": daily_pct,
        "cap_pct": cap_pct,
        "uncapped_damages": damages["uncapped"],
        "damages_cap": damages["cap"],
        "delay_damages": damages["damages"],
        "cap_reached": damages["cap_reached"],
        "cap_approaching": bool(damages["cap"] and damages["uncapped"] >= 0.8 * damages["cap"]),
        "clauses": {
            "time_for_completion": contract_data.clause_number("time_for_completion"),
            "delay_damages": contract_data.clause_number("delay_damages"),
        },
        "citation": contract_data.CONTRACT_DOCUMENT,
        "assumption": assumption,
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    _support.write_artifact(workspace, f"delay_{stem}.json", assessment)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "contract-administrator"
    tenant = _support.text_of(record, "_tenant_id") or "local"

    inputs: Dict[str, Dict[str, Any]] = {
        "cpm_engine": {
            "activities": _schedule_activities(reference, delay_days, extension_days),
            "project_start": (commencement or assessment_date).isoformat(),
        },
        "formula_executor": {
            "formula_description": "a per-day fee on an amount capped at a percentage of that amount",
            "input_values": {
                "accepted_contract_amount": accepted,
                "daily_rate_pct": daily_pct,
                "delay_days": float(delay_days),
                "cap_pct": cap_pct,
            },
        },
        "transaction_state_machine": {
            "entity_id": reference,
            "vertical": "task",
        },
        "notification": {
            "channel": "mcp",
            "block": "audit",
            "tool": "audit",
            "topic": "delay_damages.assessed",
            "message": f"Delay exposure for {reference}: {delay_days} day(s), damages {damages['damages']}",
            "payload": assessment,
        },
        "evidence_chain": {
            "tenant_id": tenant,
            "action_type": "delay_damages_assessed",
            "principal_id": principal,
            "payload": assessment,
            "result": {"delay_damages": damages["damages"], "cap_reached": damages["cap_reached"]},
            "reference": reference,
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"transaction_state_machine": "allowed"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    result = {
        **assessment,
        "currency": contract_data.currency_label(),
        "assessment_file": _support.artifact_name("delay", assessment),
        "block_evidence": {
            "schedule_computed": isinstance(answers.get("cpm_engine"), dict)
            and answers["cpm_engine"].get("ok") is not False,
            "formula_checked": isinstance(answers.get("formula_executor"), dict)
            and answers["formula_executor"].get("ok") is not False,
            "state_checked": isinstance(answers.get("transaction_state_machine"), dict)
            and answers["transaction_state_machine"].get("ok") is not False,
            "notice_raised": isinstance(answers.get("notification"), dict)
            and answers["notification"].get("ok") is not False,
            "evidence_chained": isinstance(answers.get("evidence_chain"), dict)
            and answers["evidence_chain"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "formula_authority": "improvised, no Store coverage",
        "authority": "improvised, no Store coverage",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
