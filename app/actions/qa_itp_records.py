"""qa_itp_records — Inspection and Test Plan records tied to BOQ work items.

An ITP record captures an inspection against a priced BOQ item from
document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx, the hold
points that stop the works until the inspection passes, and the sign-off that
releases them. Each record is chained as evidence and logged.

READS:  the capability payload, the BOQ, block answers.
WRITES: the record returned to the route (the route persists it).
NEVER:  releases a hold point without a named sign-off, or answers ok around
        a failed block.
"""

from __future__ import annotations

from typing import Any, Dict

from app import contract, dispatch, models, security
from app.actions._common import (
    BlockRefused,
    as_date,
    call,
    digest,
    envelope,
    refusal,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["document_engine", "evidence_chain", "audit"]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_BOQ = "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx"
_CONTRACT = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"


def _itp_text(data: Dict[str, Any], item: Dict[str, Any] | None) -> str:
    number = str(data.get("itp_number") or "ITP")
    kind = str(data.get("inspection_type") or "workmanship")
    description = str((item or {}).get("description") or "the works")
    unit = str((item or {}).get("unit") or "")
    return (
        f"Inspection and Test Plan {number}. Inspection type {kind} against "
        f"{description} ({unit}) priced in {_BOQ}. Hold point: "
        f"{'yes' if data.get('hold_point') else 'no'}. "
        f"Result recorded: {data.get('result') or 'pending'}."
    )


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.QAItpRecord.from_dict(data)
    record = model.to_dict()

    code = str(data.get("boq_item_code") or "").strip()
    item = contract.boq_item(code) if code else None
    if code and item is None:
        return refusal(f"no BOQ item {code!r} in {_BOQ}", field="boq_item_code")

    result = str(data.get("result") or "pending")
    hold_point = bool(data.get("hold_point"))
    signed_off_by = str(data.get("signed_off_by") or "").strip()
    if hold_point and result == "pass" and not signed_off_by:
        return refusal(
            "a hold point cannot be released without a named sign-off",
            field="signed_off_by",
            status=409,
        )
    if signed_off_by and result in {"pass", "conditional"}:
        security.require_approver(signed_off_by, "inspection sign-off")

    text = _itp_text(data, item)
    reference = str(data.get("reference") or data.get("itp_number") or "itp")
    try:
        parsed = call(
            "document_engine",
            {"text": text, "document_id": reference, "document_type": "itp"},
            action=None,
        )
        evidence = call(
            "evidence_chain",
            {
                "tenant_id": str(tenant_id),
                "action_type": "qa_itp_record",
                "principal_id": signed_off_by or "qa-engineer",
                "payload": {
                    "itp_number": data.get("itp_number"),
                    "boq_item_code": code,
                    "text_digest": digest(text),
                },
                "result": {"result": result, "hold_point": hold_point},
            },
            action="record",
        )
        logged = call(
            "audit",
            {
                "tenant_id": str(tenant_id),
                "action": "qa_itp_recorded",
                "resource_type": "qa_itp_record",
                "resource_id": reference,
                "status": result,
                "details": {"boq_item_code": code, "hold_point": hold_point},
            },
            action="log",
        )
    except BlockRefused as exc:
        return refusal(exc.message)

    chain_record = evidence.get("record") if isinstance(evidence.get("record"), dict) else {}
    result_body = {
        "inspection": {
            "itp_number": data.get("itp_number"),
            "boq_item_code": code or "unpriced",
            "description": str((item or {}).get("description") or ""),
            "inspection_type": data.get("inspection_type"),
            "hold_point": hold_point,
            "inspection_date": (as_date(data.get("inspection_date")) or "").isoformat()
            if as_date(data.get("inspection_date"))
            else None,
            "result": result,
            "released": bool(hold_point and result in {"pass", "conditional"} and signed_off_by),
            "signed_off_by": signed_off_by or None,
            "boq_document": _BOQ,
        },
        "document": {
            "documents_parsed": parsed.get("documents_parsed"),
            "requirements": len(parsed.get("requirements") or []),
            "engine": (parsed.get("project_metadata") or {}).get("engine_name"),
        },
        "evidence": {
            "id": chain_record.get("id"),
            "payload_hash": chain_record.get("payload_hash"),
            "chain_hash": chain_record.get("chain_hash"),
        },
        "audit": {"entry_id": (logged.get("entry") or {}).get("id"), "action": "qa_itp_recorded"},
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": _BOQ,
            "divergences": [] if item else [{"layer": "procedures", "source": _CONTRACT}],
        },
    }
    if hold_point and result == "pending":
        record["status"] = "in_progress"
    elif result == "pass" and signed_off_by:
        record["status"] = "closed"
    else:
        record["status"] = record.get("status") or "open"
    return envelope(record, result_body)
