"""Inspection and Test Plan records, hold points and sign-offs.

Each ITP record is linked to its BOQ item and document, run through the
inspection pipeline, reviewed for its recorded verdict, and sealed on the
audit chain so the quality evidence is auditable.
"""

from __future__ import annotations

from app import contract_terms as terms
from app.actions._support import (
    as_date, block_result, check, input_digest, iso, ok, principal,
    require_payload, tenant_id,
)
from app.block_inputs import default_block_action
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["workflow", "review", "document_engine", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "app.contract_terms"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]


def _pipeline(payload, itp_number):
    inspection_date = iso(as_date(payload.get("inspection_date")))
    document_reference = str(payload.get("document_reference") or terms.document_citation(terms.CONTRACT_FILENAME))
    return {
        "pipeline_id": "itp-%s" % itp_number,
        "steps": [
            {
                "id": "step_0",
                "block": "review",
                "params": {"action": "get_reviews"},
                "input": {
                    "block_id": itp_number,
                    "limit": 10,
                },
            },
            {
                "id": "step_1",
                "block": "audit_chain",
                "params": {"action": "record_evidence"},
                "input": {
                    "tenant_id": tenant_id(),
                    "action_execution_id": "itp-%s" % itp_number,
                    "action_type": "itp_inspection",
                    "principal_id": principal(),
                    "project_id": "harbourline-civil-works",
                    "payload": {
                        "itp_number": itp_number,
                        "boq_item": payload.get("boq_item"),
                        "inspection_date": inspection_date,
                        "document_reference": document_reference,
                    },
                    "result": {"result": payload.get("result") or "", "hold_point": bool(payload.get("hold_point"))},
                },
            },
        ],
    }


def handle(payload):
    payload = require_payload(payload)
    itp_number = str(payload.get("itp_number") or payload.get("reference") or "itp")
    boq_item = terms.boq_item(str(payload.get("boq_item") or ""))
    boq_citation = (
        terms.boq_citation(boq_item["item"]) if boq_item else terms.document_citation(terms.BOQ_FILENAME)
    )

    pipeline_answer = execute(
        "workflow",
        _pipeline(payload, itp_number),
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

    review_answer = execute(
        "review",
        {"block_id": itp_number, "limit": 10},
        action=BLOCK_DEFAULT_ACTIONS.get("review"),
    )
    stopped = check("review", review_answer)
    if stopped:
        return stopped
    review = block_result(review_answer)

    narrative = (
        "Inspection and Test Plan %s for BOQ item %s (%s). Inspection type: %s. "
        "Date: %s. Recorded result: %s. Hold point: %s."
        % (
            itp_number,
            payload.get("boq_item") or "unlinked",
            boq_citation,
            payload.get("inspection_type") or "inspection",
            iso(as_date(payload.get("inspection_date"))),
            payload.get("result") or "not recorded",
            "yes" if payload.get("hold_point") else "no",
        )
    )
    document_answer = execute(
        "document_engine",
        {"text": narrative},
        action=BLOCK_DEFAULT_ACTIONS.get("document_engine"),
    )
    stopped = check("document_engine", document_answer)
    if stopped:
        return stopped
    document = block_result(document_answer)

    audit_answer = execute(
        "audit_chain",
        {
            "tenant_id": tenant_id(),
            "action_execution_id": "itp-%s-signoff" % itp_number,
            "action_type": "itp_signoff",
            "principal_id": principal(),
            "project_id": "harbourline-civil-works",
            "payload": {"itp_number": itp_number, "document": narrative},
            "result": {"steps": len(steps), "reviews": len(review.get("reviews") or [])},
        },
        action=BLOCK_DEFAULT_ACTIONS.get("audit_chain"),
    )
    stopped = check("audit_chain", audit_answer)
    if stopped:
        return stopped
    audit = block_result(audit_answer)

    hold_point = bool(payload.get("hold_point"))
    result_text = str(payload.get("result") or "")
    verdict = "hold" if hold_point else ("pass" if result_text else "pending")

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "itp_number": itp_number,
            "boq_item": payload.get("boq_item") or "",
            "verdict": verdict,
            "pipeline_status": pipeline.get("status"),
            "pipeline_steps": len(steps),
            "signed_off_by": principal(),
            "reviews_recorded": len(review.get("reviews") or []),
            "document_requirements": len(document.get("requirements") or []),
            "audit_chain_hash": (audit.get("record") or {}).get("chain_hash"),
            "input_digest": input_digest(payload),
            "citations": [boq_citation, terms.clause_citation(terms.DEFECTS_NOTIFICATION)],
            "authority": "documents (layer 2, precedence.v1)",
        }
    )
