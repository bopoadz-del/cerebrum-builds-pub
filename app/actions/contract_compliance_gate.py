"""contract_compliance_gate -- gate submissions against the pinned terms.

Gates each claim, notification and taking-over submission against the pinned
contract clauses and BOQ schedule, refusing or escalating records that
conflict with Time for Completion, retention, security or the Defects
Notification Period.

Scope READS: caller payload, app/sources.py, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only.
Scope NEVER: no network, no invented clause value, no passing an unevidenced
submission.
"""

from __future__ import annotations

from typing import Any, Dict

from app import formulas, sources
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    number_of,
    record_of,
    refusal,
    success,
    tenant_scope,
    text_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "contract_compliance_gate"
ENTITY = CAPABILITY_ID

BLOCK_IDS = ["validation", "governance_gate", "evidence_or_refuse", "rule_intent_router", "audit_fail_closed"]

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "validation": "validate_pipeline",
    "governance_gate": "create_request",
    "evidence_or_refuse": "judge",
    "rule_intent_router": "stats",
    "audit_fail_closed": "record",
}

AUTHORITY = authority(CAPABILITY_ID, 1, "certified")

#: Which contract term governs each submission kind, and what it means.
_RULE = {
    "progress_claim": ("retention", "retention percent withheld on each IPC"),
    "notification": ("defects_notification", "defects notification period in days"),
    "taking_over": ("time_for_completion", "time for completion in days"),
}

_TERM = {
    "retention": "retention_percent",
    "defects_notification": "days",
    "time_for_completion": "days",
}


def _expected(term: str) -> float:
    return float(sources.clause_value(term))


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    submission_type = text_of(record.get("submission_type")) or "progress_claim"
    submission_ref = text_of(record.get("submission_ref")) or text_of(record.get("reference")) or "submission"
    checked_by = text_of(record.get("checked_by")) or "contract-administrator"

    term, requirement = _RULE.get(submission_type, ("retention", "governed value"))
    clause_ref = text_of(record.get("clause_ref"))
    pinned = sources.clause(clause_ref)
    if pinned is not None and clause_ref != "":
        term = str(pinned.get("key") or term)
    clause_number = sources.clause_number(term)
    expected = _expected(term) if term in _TERM else _expected("retention")

    proposed_text = text_of(record.get("proposed_value"))
    try:
        proposed = float(proposed_text)
    except (TypeError, ValueError):
        proposed = None

    if proposed is None:
        decision = "escalate"
        reason = (
            "the submission states no comparable value for Clause %s; a "
            "person must check it against %s"
            % (clause_number, requirement)
        )
    elif abs(proposed - expected) <= 0.0001:
        decision = "pass"
        reason = "the stated value matches Clause %s (%s)" % (clause_number, expected)
    else:
        decision = "refuse"
        reason = (
            "the stated value %s conflicts with Clause %s (%s)"
            % (proposed, clause_number, expected)
        )

    digest_ref = record.get("_input_digest") or submission_ref
    inputs: Dict[str, Dict[str, Any]] = {
        "validation": {
            "item": {
                "id": submission_ref,
                "type": submission_type,
                "quantity": max(1.0, abs(proposed) if proposed is not None else 1.0),
                "unit": "sum",
                "value": proposed if proposed is not None else expected,
            }
        },
        "governance_gate": {
            "action": "create_request",
            "tenant_id": tenant_scope(),
            "action_type": "contract_compliance_gate",
            "target_id": "gate-%s" % digest_ref,
            "requester_id": checked_by,
            "payload": {"submission": submission_ref, "clause": clause_number},
        },
        "evidence_or_refuse": {
            "action": "judge",
            "claims": [
                {
                    "id": "clause-%s" % clause_number,
                    "claim": "%s against Clause %s" % (submission_type, clause_number),
                    "evidence": [sources.CONTRACT_DOCUMENT + "#" + clause_number],
                }
            ],
        },
        "rule_intent_router": {"action": "stats", "days": 7},
        "audit_fail_closed": {
            "action": "record",
            "actor": checked_by,
            "role": "operator",
            "method": "POST",
            "path": "/v1/contract_compliance_gate",
            "status_code": 200,
            "detail": "%s %s: %s" % (submission_ref, clause_number, decision),
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
            "submission_ref": submission_ref,
            "submission_type": submission_type,
            "clause": clause_number,
            "requirement": requirement,
            "expected": expected,
            "proposed": proposed,
            "decision": decision,
            "reason": reason,
            "checked_by": checked_by,
            "citation": "%s#%s" % (sources.CONTRACT_DOCUMENT, clause_number),
            "boq_total": formulas.money(sources.accepted_contract_amount()),
        },
    )
