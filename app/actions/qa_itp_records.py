"""qa_itp_records -- Inspection and Test Plan records with an evidence trail.

One record covers one inspection lot against a BOQ item: the inspection
date, hold and witness points, the test verdict, the sign-off and any defect
close-out. The record is parsed as a technical document, listed as an
inspection task, chained into the evidence ledger and mirrored to the audit
chain.

READS   the request record, the BOQ line and the contract's Defects
        Notification Period (Clause 11.1).
WRITES  evidence artifacts under STORAGE_PATH/workspace; the ROUTE persists
        the ITP record, never this handler.
NEVER   marks a failed lot accepted, and never invents a sign-off.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from app import contract_data
from app import capability_support as _support
from app.capability_support import as_date, ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["document_engine", "task_listing", "evidence_chain", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}


def _itp_text(record: Dict[str, Any], line: Dict[str, Any], reference: str) -> str:
    lot = _support.text_of(record, "inspection_lot") or reference
    item = str(line.get("item") or "")
    description = str(line.get("description") or "")
    return (
        f"Inspection and Test Plan record {reference}\n"
        f"BOQ item: {item} {description}\n"
        f"Inspection lot: {lot}\n"
        f"Test result: {_support.text_of(record, 'test_result') or 'pending'}\n"
        f"Hold point: {_support.text_of(record, 'hold_point') or 'none recorded'}\n"
        f"Witness point: {_support.text_of(record, 'witness_point') or 'none recorded'}\n"
        f"Sign-off: {_support.text_of(record, 'signoff_by') or 'not signed'}\n"
        f"Defects notification period: {contract_data.DEFECTS_NOTIFICATION_DAYS} days "
        f"from Taking-Over (Clause {contract_data.clause_number('defects_notification')})."
    )


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "qa-inspector"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"

    item_code = _support.text_of(record, "boq_item").upper()
    line = contract_data.boq_item(item_code) if item_code else None
    if item_code and line is None:
        return refuse(
            f"BOQ item {item_code!r} is not in document:{contract_data.BOQ_DOCUMENT}",
            error_kind="unknown_boq_item",
            input_digest=input_digest,
        )

    test_result = (_support.text_of(record, "test_result") or "pending").lower()
    accepted = test_result == "pass"
    nonconformance = test_result == "fail"
    inspection_date = as_date(record.get("inspection_date"))
    taking_over = as_date(record.get("taking_over_date"))
    defect_close = as_date(record.get("defect_close_out_date"))
    dnp = contract_data.DEFECTS_NOTIFICATION_DAYS
    liability_end = taking_over + timedelta(days=dnp) if taking_over else None
    close_out_within_dnp = None
    if liability_end is not None and defect_close is not None:
        close_out_within_dnp = defect_close <= liability_end
    elif liability_end is not None:
        close_out_within_dnp = None

    signoff = _support.text_of(record, "signoff_by")
    if accepted and not signoff:
        return refuse(
            "a passing inspection lot must name the person who signed it off",
            error_kind="missing_signoff",
            input_digest=input_digest,
        )

    assessment = {
        "reference": reference,
        "boq_item": item_code or None,
        "description": str((line or {}).get("description") or ""),
        "inspection_lot": _support.text_of(record, "inspection_lot") or reference,
        "inspection_date": inspection_date.isoformat() if inspection_date else None,
        "test_result": test_result,
        "lot_accepted": accepted,
        "nonconformance": nonconformance,
        # A hold point holds the work until the inspection is signed off; the
        # record states whether it has been released, not only that it exists.
        "hold_point_state": (
            "not_required" if not _support.text_of(record, "hold_point")
            else ("released" if signoff else "open")
        ),
        "witness_point_state": (
            "not_required" if not _support.text_of(record, "witness_point")
            else ("attended" if inspection_date else "scheduled")
        ),
        "nonconformance_open": bool(
            nonconformance and defect_close is None
        ),
        "hold_point": _support.text_of(record, "hold_point"),
        "witness_point": _support.text_of(record, "witness_point"),
        "signoff_by": signoff,
        "defect_ref": _support.text_of(record, "defect_ref"),
        "taking_over_date": taking_over.isoformat() if taking_over else None,
        "defects_notification_days": dnp,
        "defects_liability_end": liability_end.isoformat() if liability_end else None,
        "defect_close_out_date": defect_close.isoformat() if defect_close else None,
        "close_out_within_defects_period": close_out_within_dnp,
        "clauses": {"defects_notification": contract_data.clause_number("defects_notification")},
        "citations": [contract_data.BOQ_DOCUMENT, contract_data.CONTRACT_DOCUMENT],
        "authority": "layer 3 formulas",
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    text = _itp_text(record, line or {}, reference)
    address = contract_data.CONTRACT_DOCUMENT

    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {"text": text},
        "task_listing": {
            "title": f"ITP inspection {reference}",
            "description": text[:2000],
            "category": "other",
            "location": {"address": address},
        },
        "evidence_chain": {
            "tenant_id": tenant,
            "action_type": "itp_recorded",
            "principal_id": principal,
            "payload": assessment,
            "result": {
                "lot_accepted": accepted,
                "test_result": test_result,
                "nonconformance": nonconformance,
            },
        },
        "audit_chain": {
            "tenant_id": tenant,
            "action_execution_id": reference,
            "action_type": "itp_recorded",
            "principal_id": principal,
            "payload": assessment,
            "result": {"lot_accepted": accepted, "test_result": test_result},
        },
    }
    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    artifact = _support.artifact_name("itp", assessment)
    _support.write_artifact(workspace, artifact, assessment)
    result = {
        **assessment,
        "itp_file": artifact,
        "block_evidence": {
            "document_parsed": isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False,
            "task_listed": isinstance(answers.get("task_listing"), dict)
            and answers["task_listing"].get("ok") is not False,
            "evidence_chained": isinstance(answers.get("evidence_chain"), dict)
            and answers["evidence_chain"].get("ok") is not False,
            "audit_chained": isinstance(answers.get("audit_chain"), dict)
            and answers["audit_chain"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
