"""qa_itp_records -- inspection and test plans tied to BOQ items.

One record is one inspection lot: the BOQ item it covers, its hold point and
witness point, the inspection date, and the test verdict. A failed or pending
lot is a real, persisted record -- the platform records the outcome, it does
not launder it into a pass.

READS   the request record, the uploaded BOQ item, and the workspace it writes
        the lot evidence into.
WRITES  the inspection evidence under STORAGE_PATH/workspace and this
        capability's result; the ROUTE persists the record, never the handler.
NEVER   marks a lot accepted unless the test result is ``pass``.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Dict

from app import contract_data
from app.actions import _support
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS
from app.actions._support import as_date, ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["workbench", "workflow", "capture", "evidence_chain", "review", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}

RATING_BY_RESULT = {"pass": 5, "pending": 3, "fail": 2}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    item_code = _support.text_of(record, "boq_item").upper()
    line = contract_data.boq_item(item_code) if item_code else None
    if item_code and line is None:
        return refuse(
            f"boq_item {item_code!r} is not in the uploaded BOQ; known items: "
            + ", ".join(item["item"] for item in contract_data.boq_lines()),
            error_kind="unknown_boq_item",
        )

    test_result = (_support.text_of(record, "test_result") or "pending").lower()
    inspection_date = as_date(record.get("inspection_date")) or date.today()
    hold_point = _support.text_of(record, "hold_point") or (
        f"Hold point: inspection lot {_support.text_of(record, 'inspection_lot') or reference}"
    )
    witness_point = _support.text_of(record, "witness_point") or (
        f"Witness point: {_support.text_of(record, 'inspection_lot') or reference}"
    )
    accepted = test_result == "pass"
    principal = _support.text_of(record, "principal_id") or "contract-administrator"

    workspace = _support.workspace_dir(CAPABILITY_ID)
    lot = {
        "reference": reference,
        "boq_item": item_code,
        "boq_description": (line or {}).get("description"),
        "inspection_lot": _support.text_of(record, "inspection_lot") or reference,
        "hold_point": hold_point,
        "witness_point": witness_point,
        "inspection_date": inspection_date.isoformat(),
        "test_result": test_result,
        "accepted": accepted,
        "citation": contract_data.BOQ_DOCUMENT,
    }
    lot_file = workspace / f"itp_{reference.replace('/', '_')}_{uuid.uuid4().hex[:8]}.json"
    lot_file.write_text(json.dumps(lot, indent=2, sort_keys=True), encoding="utf-8")

    workflow_step = {
        "id": "step_0",
        "block": "audit",
        "action": "log",
        "input": {
            "action_type": "itp_inspection",
            "principal_id": principal,
            "topic": "itp.inspected",
            "message": f"ITP {reference} recorded with result {test_result}",
            "channel": "mcp",
            "tool": "audit",
            "payload": lot,
            "result": {"reference": reference, "accepted": accepted},
        },
    }
    inputs: Dict[str, Dict[str, Any]] = {
        "workbench": {
            "brief": (
                f"Inspect the ITP evidence for {reference} against BOQ item {item_code or 'unreferenced'}; "
                f"hold point {hold_point}; result {test_result}."
            ),
            "mutable_paths": [str(workspace)],
        },
        "workflow": {
            "pipeline_id": f"itp:{reference}",
            "steps": [workflow_step],
            "result": {"reference": reference, "accepted": accepted, "test_result": test_result},
            "topic": "itp.inspected",
            "channel": "mcp",
            "tool": "workflow",
        },
        "capture": {"text": json.dumps(lot, sort_keys=True), "reference": reference},
        "evidence_chain": {
            "tenant_id": _support.text_of(record, "_tenant_id") or "local",
            "action_type": "itp_inspection",
            "principal_id": principal,
            "payload": lot,
            "result": {"accepted": accepted, "test_result": test_result},
        },
        "review": {
            "block_id": reference,
            "user_id": principal,
            "rating": RATING_BY_RESULT.get(test_result, 3),
            "review_text": f"ITP {reference}: {hold_point}; result {test_result}",
        },
        "audit_chain": {
            "action_execution_id": f"itp:{reference}",
            "action_type": "itp_inspection",
            "principal_id": principal,
            "payload": lot,
            "result": {"accepted": accepted, "test_result": test_result},
        },
    }

    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID, record, BLOCK_IDS, inputs, actions={"review": "submit_review"}
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result = {
        **lot,
        "inspection_status": "accepted" if accepted else ("rejected" if test_result == "fail" else "pending"),
        "block_evidence": {
            "workbench_inspected": isinstance(answers.get("workbench"), dict)
            and answers["workbench"].get("ok") is not False,
            "workflow_completed": isinstance(answers.get("workflow"), dict)
            and answers["workflow"].get("ok") is not False,
            "captured": isinstance(answers.get("capture"), dict)
            and answers["capture"].get("ok") is not False,
            "chained": isinstance(answers.get("evidence_chain"), dict)
            and answers["evidence_chain"].get("ok") is not False,
            "reviewed": isinstance(answers.get("review"), dict)
            and answers["review"].get("ok") is not False,
        },
        "evidence_file": str(lot_file),
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 3 formulas",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
