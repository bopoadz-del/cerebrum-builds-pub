"""Time for Completion and Delay Damages under Clauses 8.2 and 8.7.

The programme is computed by the CPM engine, the damages by the kernel's
late-fee identity over the Clause 8.7 rate and cap, and the notice is
recorded on the evidence chain and advanced through its lifecycle.
"""

from __future__ import annotations

from app import contract_terms as terms
from app import formulas
from app.actions._support import (
    as_date, as_float, as_int, block_result, check, input_digest, iso, ok,
    principal, require_payload, round_money, tenant_id,
)
from app.block_inputs import default_block_action
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["cpm_engine", "formula_executor", "evidence_chain", "transaction_state_machine"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "app.contract_terms", "app.formulas"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]


def _programme(commencement, delay_days):
    delay = max(0, as_int(delay_days))
    return {
        "project_start": iso(commencement),
        "activities": [
            {
                "id": "WORKS",
                "name": "Time for Completion (contract clause %s)" % terms.TIME_FOR_COMPLETION,
                "duration": int(terms.TIME_FOR_COMPLETION_DAYS),
                "predecessors": [],
            },
            {
                "id": "DELAY",
                "name": "Delay event under contract clause %s" % terms.DELAY_DAMAGES,
                "duration": delay,
                "predecessors": [{"predecessor_id": "WORKS", "type": "FS", "lag": 0}],
            },
        ],
    }


def handle(payload):
    payload = require_payload(payload)
    commencement = as_date(payload.get("commencement_date"))
    delay_days = as_float(payload.get("delay_days"))
    extension_days = as_float(payload.get("extension_days"))
    net_delay = max(0.0, delay_days - extension_days)

    cpm_answer = execute(
        "cpm_engine",
        _programme(commencement, net_delay),
        action=BLOCK_DEFAULT_ACTIONS.get("cpm_engine"),
    )
    stopped = check("cpm_engine", cpm_answer)
    if stopped:
        return stopped
    programme = block_result(cpm_answer)

    accepted = as_float(payload.get("accepted_contract_amount")) or terms.ACCEPTED_CONTRACT_AMOUNT
    planned_fraction = max(0.0, min(1.0, as_int(programme.get("project_duration")) / float(terms.TIME_FOR_COMPLETION_DAYS or 1)))
    earned_answer = execute(
        "formula_executor",
        {
            "formula_key": "earned_value",
            "input_values": {
                "bac": accepted,
                "pv": accepted * planned_fraction,
                "ev": accepted * max(0.0, planned_fraction - net_delay / float(terms.TIME_FOR_COMPLETION_DAYS or 1)),
                "ac": accepted,
            },
        },
        action=BLOCK_DEFAULT_ACTIONS.get("formula_executor"),
    )
    stopped = check("formula_executor", earned_answer)
    if stopped:
        return stopped
    earned_answer_body = block_result(earned_answer)
    earned = (
        earned_answer_body.get("execution_result")
        if isinstance(earned_answer_body.get("execution_result"), dict)
        else earned_answer_body
    )

    notice_reference = str(payload.get("notice_reference") or payload.get("reference") or "delay-notice")
    damages = formulas.delay_damages(accepted, net_delay)

    evidence_answer = execute(
        "evidence_chain",
        {
            "tenant_id": tenant_id(),
            "action_execution_id": notice_reference,
            "action_type": "delay_damages_assessment",
            "principal_id": principal(),
            "project_id": "harbourline-civil-works",
            "payload": {
                "delay_days": delay_days,
                "extension_days": extension_days,
                "clause": terms.DELAY_DAMAGES,
            },
            "result": {"damages": damages["value"], "capped": damages["capped"]},
        },
        action=BLOCK_DEFAULT_ACTIONS.get("evidence_chain"),
    )
    stopped = check("evidence_chain", evidence_answer)
    if stopped:
        return stopped
    evidence = block_result(evidence_answer)

    lifecycle_answer = execute(
        "transaction_state_machine",
        {
            "entity_id": notice_reference,
            "vertical": "transaction",
            "event": "post_offers",
            "actor": "provider",
        },
        action=BLOCK_DEFAULT_ACTIONS.get("transaction_state_machine"),
    )
    stopped = check("transaction_state_machine", lifecycle_answer)
    if stopped:
        return stopped
    lifecycle = block_result(lifecycle_answer)

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "net_delay_days": net_delay,
            "time_for_completion_days": terms.TIME_FOR_COMPLETION_DAYS,
            "project_duration_days": programme.get("project_duration"),
            "critical_path": programme.get("critical_path"),
            "schedule_performance_index": earned.get("spi"),
            "cost_performance_index": earned.get("cpi"),
            "delay_damages_amount": round_money(damages["value"]),
            "delay_damages_uncapped": round_money(damages["uncapped_value"]),
            "delay_damages_cap": round_money(damages["cap"]),
            "cap_applied": damages["capped"],
            "exposure_ratio": round(damages["value"] / accepted, 6) if accepted else 0.0,
            "evidence_chain_hash": (evidence.get("record") or {}).get("chain_hash"),
            "lifecycle_state": lifecycle.get("to_state"),
            "cap_boundary_hit": damages["capped"],
            "input_digest": input_digest(payload),
            "citations": [
                terms.clause_citation(terms.TIME_FOR_COMPLETION),
                terms.clause_citation(terms.DELAY_DAMAGES),
            ],
            "authority": "formulas (layer 3, precedence.v1)",
        }
    )
