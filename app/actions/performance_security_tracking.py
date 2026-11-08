"""The Clause 4.2 Performance Security: issuance, expiry, renewal, cover.

The required amount is the Clause 4.2 percentage of the Accepted Contract
Amount; coverage and days-to-expiry are computed on every record. A security
inside its renewal window or below its required cover raises a notification.
"""

from __future__ import annotations

from datetime import date

from app import contract_terms as terms
from app import formulas
from app.actions._support import (
    as_date, as_float, as_int, block_result, check, input_digest, iso, ok,
    principal, require_payload, round_money, tenant_id,
)
from app.block_inputs import default_block_action
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "performance_security_tracking"
ENTITY = "performance_security_tracking"
BLOCK_IDS = ["workflow", "notification", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "app.contract_terms", "app.formulas"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]


def _pipeline(payload, reference, coverage):
    return {
        "pipeline_id": "security-%s" % reference,
        "steps": [
            {
                "id": "step_0",
                "block": "audit_chain",
                "params": {"action": "record_evidence"},
                "input": {
                    "tenant_id": tenant_id(),
                    "action_execution_id": "security-%s" % reference,
                    "action_type": "performance_security_review",
                    "principal_id": principal(),
                    "project_id": "harbourline-civil-works",
                    "payload": {"reference": reference, "coverage": coverage},
                    "result": {"status": payload.get("status")},
                },
            },
        ],
    }


def handle(payload):
    payload = require_payload(payload)
    reference = str(payload.get("security_number") or payload.get("reference") or "security")
    accepted = as_float(payload.get("accepted_contract_amount")) or terms.ACCEPTED_CONTRACT_AMOUNT
    requirement = formulas.performance_security_requirement(accepted)
    required_amount = as_float(payload.get("required_amount")) or requirement["value"]
    secured_amount = as_float(payload.get("secured_amount"))
    coverage = (secured_amount / required_amount) if required_amount else 0.0

    pipeline_answer = execute(
        "workflow",
        _pipeline(payload, reference, coverage),
        action=BLOCK_DEFAULT_ACTIONS.get("workflow"),
    )
    stopped = check("workflow", pipeline_answer)
    if stopped:
        return stopped
    pipeline = block_result(pipeline_answer)
    steps = list(pipeline.get("results") or [])
    failed_steps = [step for step in steps if str(step.get("status")) not in ("success", "ok")]
    if failed_steps:
        return {
            "ok": False,
            "error": "workflow step refused: %s" % (failed_steps[0].get("error") or failed_steps[0].get("step_id")),
            "block": "workflow",
            "source": {"steps": steps},
        }

    expiry = as_date(payload.get("expiry_date"))
    days_to_expiry = max(0, (expiry - date.today()).days)
    notice_days = as_int(payload.get("renewal_notice_days")) or 30
    renewal_due = days_to_expiry <= notice_days
    below_cover = coverage < 1.0

    notice_answer = execute(
        "notification",
        {
            "channel": "mcp",
            "block": "analytics",
            "tool": "analytics",
            "params": {"action": "track_event"},
            "payload": {
                "metric": "performance_security.coverage",
                "value": coverage,
                "tags": {"security": reference, "renewal_due": renewal_due},
            },
            "message": "Performance security %s coverage %.2f, expiry %s"
            % (reference, coverage, iso(expiry)),
        },
        action=BLOCK_DEFAULT_ACTIONS.get("notification"),
    )
    stopped = check("notification", notice_answer)
    if stopped:
        return stopped
    notice = block_result(notice_answer)

    audit_answer = execute(
        "audit_chain",
        {
            "tenant_id": tenant_id(),
            "action_execution_id": "security-%s-audit" % reference,
            "action_type": "performance_security_tracking",
            "principal_id": principal(),
            "project_id": "harbourline-civil-works",
            "payload": {"reference": reference, "required_amount": required_amount},
            "result": {"coverage": coverage, "renewal_due": renewal_due},
        },
        action=BLOCK_DEFAULT_ACTIONS.get("audit_chain"),
    )
    stopped = check("audit_chain", audit_answer)
    if stopped:
        return stopped
    audit = block_result(audit_answer)

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "required_amount": round_money(required_amount),
            "secured_amount": round_money(secured_amount),
            "coverage_ratio": round(coverage, 4),
            "below_required_cover": below_cover,
            "days_to_expiry": days_to_expiry,
            "renewal_notice_days": notice_days,
            "renewal_due": renewal_due,
            "notice_sent": bool(notice.get("sent")),
            "pipeline_status": pipeline.get("status"),
            "audit_chain_hash": (audit.get("record") or {}).get("chain_hash"),
            "input_digest": input_digest(payload),
            "citations": [terms.clause_citation(terms.PERFORMANCE_SECURITY)],
            "authority": "documents (layer 2, precedence.v1)",
        }
    )
