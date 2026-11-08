"""qa_itp_records -- the Inspection and Test Plan register and its records.

Holds inspection records against BOQ work items, capturing hold points,
witness points, sign-off and evidence so QA status can be cited in claims and
taking-over submissions.

Scope READS: caller payload, app/sources.py, the vendored blocks.
Scope WRITES: caller output only.
Scope NEVER: no network, no invented inspection result, no evidence that was
not supplied.
"""

from __future__ import annotations

from typing import Any, Dict

from app import sources
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    record_of,
    refusal,
    success,
    tenant_scope,
    text_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "qa_itp_records"
ENTITY = CAPABILITY_ID

BLOCK_IDS = ["workflow", "approval_rules", "evidence_chain", "capture", "document_engine", "audit"]

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "workflow": "run",
    "approval_rules": "ledger",
    "evidence_chain": "record",
    "capture": "capture",
    "document_engine": None,
    "audit": "log",
}

AUTHORITY = authority(CAPABILITY_ID, 2, "documents")


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    item = sources.boq_item(record.get("boq_item"))
    itp_number = text_of(record.get("itp_number")) or text_of(record.get("reference")) or "ITP-draft"
    signed_off_by = text_of(record.get("signed_off_by")) or "qa-lead"
    evidence_ref = text_of(record.get("evidence_ref")) or "pending"
    inspection_date = text_of(record.get("inspection_date"))
    result = text_of(record.get("result")) or "hold"
    summary = (
        "ITP %s | BOQ %s | %s | result=%s | evidence=%s | signed=%s"
        % (
            itp_number,
            text_of(record.get("boq_item")) or (item["item"] if item else "unassigned"),
            inspection_date or "undated",
            result,
            evidence_ref,
            signed_off_by,
        )
    )

    inputs: Dict[str, Dict[str, Any]] = {
        "workflow": {
            "pipeline_id": "itp-record-%s" % itp_number,
            "trigger": "qa_itp_recorded",
            "steps": [
                {
                    "block": "event_bus",
                    "action": "publish",
                    "input": {
                        "topic": "qa_itp.recorded",
                        "payload": {
                            "itp_number": itp_number,
                            "boq_item": text_of(record.get("boq_item")),
                            "result": result,
                        },
                        "message": summary,
                        "channel": "mcp",
                        "tool": "event_bus",
                    },
                }
            ],
        },
        "approval_rules": {
            "action": "ledger",
            "project_id": text_of(record.get("reference")) or "harbourline",
            "source_doc": sources.BOQ_DOCUMENT,
        },
        "evidence_chain": {
            "action": "record",
            "tenant_id": tenant_scope(),
            "action_type": "itp_inspection",
            "principal_id": signed_off_by,
            "payload": {
                "itp_number": itp_number,
                "boq_item": text_of(record.get("boq_item")),
                "inspection_date": inspection_date,
            },
            "result": {"result": result, "evidence_ref": evidence_ref},
        },
        "capture": {
            "filename": "itp-%s.txt" % itp_number.replace("/", "-"),
            "content": summary,
            "content_type": "text/plain",
        },
        "document_engine": {"text": summary},
        "audit": {
            "action_name": "qa_itp_recorded",
            "actor": signed_off_by,
            "resource_type": "qa_itp_record",
            "resource_id": itp_number,
            "status": "ok",
            "details": {"boq_item": text_of(record.get("boq_item")), "result": result},
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

    evidence = answers.get("evidence_chain") or {}
    chain_hash = evidence.get("chain_hash") or evidence.get("hash") or None
    return success(
        CAPABILITY_ID,
        AUTHORITY,
        answers,
        input_digest=record.get("_input_digest"),
        result={
            "itp_number": itp_number,
            "boq_item": text_of(record.get("boq_item")) or (item["item"] if item else ""),
            "boq_description": item["description"] if item else "",
            "inspection_type": text_of(record.get("inspection_type")),
            "hold_point": bool(record.get("hold_point")),
            "witness_point": bool(record.get("witness_point")),
            "inspection_date": inspection_date,
            "result": result,
            "evidence_ref": evidence_ref,
            "signed_off_by": signed_off_by,
            "chain_hash": chain_hash,
            "can_cite_in_claim": result == "pass" and evidence_ref not in ("", "pending"),
            "citation": sources.BOQ_DOCUMENT,
        },
    )
