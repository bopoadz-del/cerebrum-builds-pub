"""qa_itp_records: inspection and test plan records per BOQ work section.

Captures inspection lots, hold and witness points and the test result,
ties the record to the Earthworks / Preliminaries item, and refuses QA
sign-off while a hold point is unreleased. The project EDMS is a declared
placeholder connector: the route answers its typed 503 before this runs.
"""

from __future__ import annotations

from typing import Any, Dict

from app import contract_data
from app.action_support import (
    BlockCallFailed,
    as_date,
    answer,
    call_block,
    refused,
)
from app.block_inputs import default_block_action

CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["construction_advisor", "evidence_chain", "validation", "workflow"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}

_PASS_RESULTS = {"pass", "passed", "accepted", "conforming"}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    item = contract_data.boq_item(str(record.get("boq_item") or ""))
    result = str(record.get("test_result") or "").strip().lower()
    conforming = result in _PASS_RESULTS
    hold_released = conforming and bool(str(record.get("hold_point") or "").strip())
    lot = str(record.get("inspection_lot") or reference)
    witness = str(record.get("witness_point") or "not-required")

    try:
        advice = call_block(
            "construction_advisor",
            {"query": f"hold point release inspection lot {lot} {item.get('description', '')}".strip()},
            action=BLOCK_DEFAULT_ACTIONS.get("construction_advisor"),
        )
        evidence = call_block(
            "evidence_chain",
            {
                "tenant_id": tenant_id,
                "action_type": "qa_itp_record",
                "principal_id": str(record.get("inspector_id") or "qa-inspector"),
                "payload": {"reference": reference, "lot": lot, "result": result},
                "result": {"conforming": conforming},
            },
            action=BLOCK_DEFAULT_ACTIONS.get("evidence_chain"),
        )
        check = call_block(
            "validation",
            {"pipeline": {"id": CAPABILITY_ID, "type": "pipeline"},
             "blocks": [CAPABILITY_ID], "required_tests": ["unit"]},
            action=BLOCK_DEFAULT_ACTIONS.get("validation"),
        )
        pipeline = call_block(
            "workflow",
            {
                "pipeline_id": "qa_itp_signoff",
                "steps": [
                    {"id": "step_0", "block": "validation", "action": "validate_pipeline",
                     "input": {"pipeline": {"id": CAPABILITY_ID, "type": "pipeline"}}},
                ],
            },
            action=BLOCK_DEFAULT_ACTIONS.get("workflow"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "inspection_lot": lot,
            "boq_item": item,
            "inspection_date": as_date(record.get("inspection_date")).isoformat(),
            "test_result": result or "pending",
            "conforming": conforming,
            "hold_point": str(record.get("hold_point") or ""),
            "hold_point_released": hold_released,
            "witness_point": witness,
            "claim_certification_gate": "open" if hold_released else "held",
            "advisor_hits": int(advice.get("count") or 0) if isinstance(advice, dict) else 0,
            "evidence_record": (evidence.get("record") or {}).get("id") if isinstance(evidence, dict) else None,
            "validation_status": check.get("status") if isinstance(check, dict) else None,
            "workflow_status": pipeline.get("status") if isinstance(pipeline, dict) else None,
            "clauses": {"11.1": contract_data.CLAUSES["11.1"]},
        },
        authority="2:documents",
    )
