"""delay_damages_tracking -- Time for Completion and Clause 8.7 exposure.

Elapsed time is measured against the contractual Time for Completion (Clause
8.2) plus any extension-of-time days the caller records. Delay damages are
the per-day percentage of the Accepted Contract Amount, capped at the
contractual percentage (Clause 8.7); the assessment names the cap when it is
reached and raises an event through the notification block.

READS   the request record, the contract terms and the BOQ total.
WRITES  the assessment under STORAGE_PATH/workspace; the ROUTE persists the
        assessment, never this handler.
NEVER   invents a commencement date, a day count or a rate: a missing figure
        is stated as an assumption instead.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app import contract_data, formulas
from app import capability_support as _support
from app.capability_support import as_date, ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["formula_executor", "notification", "audit"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

#: A threshold is "approached" at four fifths of it. The owner of the rate
#: and the cap is the contract; this is the platform's alerting convention,
#: stated once so every milestone uses the same fraction.
ALERT_THRESHOLD = 0.8

#: The per-day fee with a hard cap is not the kernel's annual-rate late-fee
#: identity; the block executes this formula over the caller's inputs.
DAMAGES_CODE = (
    "rate = accepted_contract_amount * (daily_rate_pct / 100.0)\n"
    "uncapped = rate * delay_days\n"
    "cap = accepted_contract_amount * (cap_pct / 100.0)\n"
    "result = min(uncapped, cap)"
)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "contract-administrator"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"

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
    if accepted <= 0:
        return refuse(
            "no Accepted Contract Amount is stated and the uploaded BOQ is empty",
            error_kind="missing_contract_amount",
            input_digest=input_digest,
        )
    daily_pct = _support.number_of(record, "daily_rate_pct", 0.0)
    if daily_pct <= 0:
        daily_pct = contract_data.DELAY_DAMAGES_DAILY_PCT
    cap_pct = _support.number_of(record, "cap_pct", 0.0)
    if cap_pct <= 0:
        cap_pct = contract_data.DELAY_DAMAGES_CAP_PCT

    # A caller figure that departs from the uploaded contract is recorded as
    # a divergence, with the document winning (the same precedence the
    # contract-terms capability states).
    divergences: List[Dict[str, Any]] = []
    if daily_pct and abs(daily_pct - contract_data.DELAY_DAMAGES_DAILY_PCT) > 1e-9:
        divergences.append(
            {
                "term": "delay_damages_daily_pct",
                "contract_value": contract_data.DELAY_DAMAGES_DAILY_PCT,
                "caller_value": daily_pct,
                "winner": "documents",
                "loser": "caller",
            }
        )
    if cap_pct and abs(cap_pct - contract_data.DELAY_DAMAGES_CAP_PCT) > 1e-9:
        divergences.append(
            {
                "term": "delay_damages_cap_pct",
                "contract_value": contract_data.DELAY_DAMAGES_CAP_PCT,
                "caller_value": cap_pct,
                "winner": "documents",
                "loser": "caller",
            }
        )

    damages = formulas.delay_damages(accepted, daily_pct, delay_days, cap_pct)

    elapsed = 0
    if commencement is not None:
        elapsed = max(0, (assessment_date - commencement).days)
    allowable = contract_data.TIME_FOR_COMPLETION_DAYS + extension_days
    alerts = []
    if allowable > 0 and elapsed >= allowable:
        alerts.append(
            {
                "kind": "time_for_completion_exceeded",
                "elapsed_days": elapsed,
                "allowable_days": allowable,
                "message": (
                    f"{elapsed} day(s) elapsed against {allowable} allowed: the "
                    "Time for Completion has been exceeded."
                ),
            }
        )
    elif allowable > 0 and elapsed >= ALERT_THRESHOLD * allowable:
        alerts.append(
            {
                "kind": "time_for_completion_approaching",
                "elapsed_days": elapsed,
                "allowable_days": allowable,
                "message": (
                    f"{elapsed} day(s) elapsed of {allowable} allowed: the Time "
                    "for Completion is being approached."
                ),
            }
        )
    cap = damages["cap"]
    if cap:
        if damages["uncapped"] >= cap:
            alerts.append(
                {
                    "kind": "cap_reached",
                    "uncapped_damages": damages["uncapped"],
                    "cap_amount": cap,
                    "message": f"Delay damages reached the Clause 8.7 cap of {cap}.",
                }
            )
        elif damages["uncapped"] >= ALERT_THRESHOLD * cap:
            alerts.append(
                {
                    "kind": "cap_approaching",
                    "uncapped_damages": damages["uncapped"],
                    "cap_amount": cap,
                    "message": (
                        f"Delay damages are within {int(ALERT_THRESHOLD * 100)}% of "
                        f"the Clause 8.7 cap of {cap}."
                    ),
                }
            )

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
        "cap_approaching": any(alert["kind"] == "cap_approaching" for alert in alerts),
        "elapsed_days": elapsed,
        "allowable_days": allowable,
        "alerts": alerts,
        "divergences": divergences,
        "clauses": {
            "time_for_completion": contract_data.clause_number("time_for_completion"),
            "delay_damages": contract_data.clause_number("delay_damages"),
        },
        "citations": [contract_data.CONTRACT_DOCUMENT],
        "assumption": assumption,
        "currency": contract_data.currency_label(),
        "formula_authority": formulas.IMPROVISED,
        "authority": formulas.IMPROVISED,
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]

    inputs: Dict[str, Dict[str, Any]] = {
        "formula_executor": {
            "formula_description": "a per-day fee on an amount, capped at a percentage of that amount",
            "input_values": {
                "accepted_contract_amount": accepted,
                "daily_rate_pct": daily_pct,
                "delay_days": float(delay_days),
                "cap_pct": cap_pct,
            },
            "custom_code": DAMAGES_CODE,
        },
        "notification": {
            "channel": "mcp",
            "block": "audit",
            "tool": "audit",
            "topic": (
                "delay_damages.alert" if alerts else "delay_damages.assessed"
            ),
            "message": (
                f"Delay exposure for {reference}: {delay_days} day(s), damages "
                f"{damages['damages']}"
                + (
                    "; alerts: " + "; ".join(alert["message"] for alert in alerts)
                    if alerts
                    else "; no threshold reached"
                )
            ),
            "payload": {**assessment, "alert_kinds": [a["kind"] for a in alerts]},
        },
        "audit": {
            "tenant_id": tenant,
            "project_id": contract_data.CONTRACT_DOCUMENT,
            "principal_id": principal,
            "action_name": "delay_damages_assessed",
            "resource_type": CAPABILITY_ID,
            "resource_id": reference,
            "status": "ok",
            "details": {
                "delay_days": delay_days,
                "delay_damages": damages["damages"],
                "cap_reached": damages["cap_reached"],
                "alert_kinds": [alert["kind"] for alert in alerts],
            },
        },
    }
    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    artifact = _support.artifact_name("delay", assessment)
    _support.write_artifact(workspace, artifact, assessment)
    result = {
        **assessment,
        "assessment_file": artifact,
        "block_evidence": {
            "formula_checked": isinstance(answers.get("formula_executor"), dict)
            and answers["formula_executor"].get("ok") is not False,
            "notice_raised": isinstance(answers.get("notification"), dict)
            and answers["notification"].get("ok") is not False,
            "audited": isinstance(answers.get("audit"), dict)
            and answers["audit"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
