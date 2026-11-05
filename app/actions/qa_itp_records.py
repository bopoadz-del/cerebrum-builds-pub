"""qa_itp_records -- inspection and test plan records tied to BOQ items.

READS  caller payload, the BOQ item catalogue and the contract document for
       the requirement citation.
WRITES the capability response envelope only.
NEVER  fabricates an inspection result, or stores a record whose document
       extraction or workflow refused.
"""

from __future__ import annotations

from app import formulas
from app.authority import authority_label
from app.block_inputs import boq_citation, block_action, contract_citation, itp_text
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["document_engine", "workflow"]

BAD_WORKFLOW = {"error", "failed", "partial", "refused"}


def _fail(block_id, answer):
    reason = answer.get("error") if isinstance(answer, dict) else answer
    return {
        "ok": False,
        "error": str(block_id) + ": " + str(reason or "block refused"),
        "block": block_id,
        "record": None,
        "id": None,
    }


def _workflow_steps(text: str, reference: str) -> list:
    """Every child is prepared; none receives the raw schema sample."""
    return [
        {
            "id": "step_0",
            "block": "document_engine",
            "input": {"text": text},
            "params": {},
        },
        {
            "id": "step_1",
            "block": "document_engine",
            "input": {"text": "Inspection requirement check for " + reference + ": " + text},
            "params": {},
        },
    ]


def handle(payload: dict) -> dict:
    data = dict(payload or {})
    reference = str(data.get("reference") or "ITP-RECORD")
    text = itp_text(data)
    item_code = str(data.get("boq_item_code") or "").strip()
    item = formulas.boq_index().get(item_code)

    try:
        extraction = execute(
            "document_engine",
            {"text": text},
            action=block_action("document_engine"),
        )
    except Exception as exc:  # noqa: BLE001
        return _fail("document_engine", {"error": f"{type(exc).__name__}: {exc}"})
    if not isinstance(extraction, dict) or str(extraction.get("status") or "").lower() == "error":
        return _fail("document_engine", extraction)

    pipeline = {
        "pipeline_id": "qa-itp-" + reference[:32],
        "steps": _workflow_steps(text, reference),
        "timeout": 60,
    }
    try:
        workflow = execute("workflow", pipeline, action=block_action("workflow"))
    except Exception as exc:  # noqa: BLE001
        return _fail("workflow", {"error": f"{type(exc).__name__}: {exc}"})
    status = str(workflow.get("status") or "").lower() if isinstance(workflow, dict) else ""
    if status in BAD_WORKFLOW:
        return _fail("workflow", workflow)

    record = {
        "id": None,
        "reference": reference,
        "status": str(data.get("status") or "open"),
        "itp_number": str(data.get("itp_number") or "ITP-" + reference),
        "inspection_type": str(data.get("inspection_type") or "hold point"),
        "boq_item_code": item_code,
        "inspection_date": data.get("inspection_date"),
        "result": str(data.get("result") or "pending"),
        "inspector": str(data.get("inspector") or ""),
        "notes": str(data.get("notes") or ""),
        "evidence_text": text,
    }
    return {
        "ok": True,
        "record": record,
        "id": None,
        "boq_item": {
            "item": item_code,
            "description": item["description"] if item else "",
            "unit": item["unit"] if item else "",
        },
        "requirement_source": {"contract": contract_citation(), "boq": boq_citation()},
        "workflow": {
            "pipeline_id": workflow.get("pipeline_id"),
            "status": workflow.get("status"),
            "steps": len(workflow.get("results") or []),
        },
        "extraction_sections": sorted(extraction.keys())[:12] if isinstance(extraction, dict) else [],
        "authority": authority_label(
            "contract",
            detail="ITP requirement from " + contract_citation() + " / " + boq_citation(),
        ),
    }
