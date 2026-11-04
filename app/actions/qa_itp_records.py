"""QA / ITP records: inspection evidence, validation stages and the chain."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["document_engine", "evidence_chain", "validation", "workflow"]


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    inspection_type = str(record.get("inspection_type") or "earthworks")
    outcome = str(record.get("outcome") or "pass")
    blocks: Dict[str, Any] = {}

    parsed, error = call("document_engine", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["document_engine"] = {"parsed": True, "sections": sorted(k for k, v in parsed.items() if v)}

    validated, error = call("validation", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    stages = validated.get("stages") or []
    failing = [stage for stage in stages if str(stage.get("status")) == "fail"]
    if failing:
        issues = "; ".join(
            str(issue) for stage in failing for issue in (stage.get("issues") or [])
        ) or "validation failed"
        return {
            "ok": False,
            "error": "record failed validation: %s" % issues[:300],
            "capability_id": CAPABILITY_ID,
        }
    blocks["validation"] = {
        "status": validated.get("status"),
        "stages": [stage.get("stage") for stage in stages],
    }

    chained, error = call("evidence_chain", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    chain = chained.get("record") if isinstance(chained.get("record"), dict) else {}
    digest = str(chain.get("payload_hash") or "")
    blocks["evidence_chain"] = {"evidence_id": chain.get("id"), "payload_hash": digest}

    pipeline, error = call("workflow", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    results = pipeline.get("results") or []
    failed_steps = [
        step for step in results
        if str(step.get("status") or "").lower() in ("failed", "error", "refused")
    ]
    if failed_steps:
        first = failed_steps[0]
        return {
            "ok": False,
            "error": "workflow step %s (%s) failed: %s"
            % (first.get("step_id"), first.get("block"), str(first.get("result"))[:200]),
            "capability_id": CAPABILITY_ID,
        }
    blocks["workflow"] = {
        "pipeline_id": pipeline.get("pipeline_id"),
        "steps": [step.get("step_id") for step in results],
        "status": pipeline.get("status"),
    }

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "inspection_type": inspection_type,
        "boq_item": str(record.get("boq_item") or ""),
        "outcome": outcome,
        "evidence_digest": digest or str(chain.get("result_hash") or ""),
        "chain_verified": bool(chain.get("payload_hash")),
    }
    computed = {
        "outcome": outcome,
        "validation_status": validated.get("status"),
        "evidence_id": chain.get("id"),
        "evidence_digest": stored["evidence_digest"],
        "chain_verified": stored["chain_verified"],
        "pipeline_status": pipeline.get("status"),
        "pipeline_steps": len(results),
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("documents"),
    }
