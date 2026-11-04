"""Contract clause governance: cite the clause, evidence it, gate its adoption."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import contract_terms
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "contract_clause_governance"
ENTITY = "contract_clause_governance"
BLOCK_IDS = ["knowledge", "regulatory_chunker", "evidence_or_refuse", "governance_gate"]


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    clause_id = str(record.get("clause_id") or reference)
    clause_type = str(record.get("clause_type") or "delay_damages")
    evidence_ref = str(record.get("evidence_ref") or "").strip()
    blocks: Dict[str, Any] = {}

    found, error = call("knowledge", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    hits = found.get("results") or []
    citations: List[str] = [
        str(hit.get("metadata", {}).get("source") or hit.get("source") or "")
        for hit in hits
    ]
    citations = [citation for citation in citations if citation]
    blocks["knowledge"] = {"hits": len(hits), "citations": citations}

    chunked, error = call("regulatory_chunker", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    chunks = chunked.get("chunks") or []
    blocks["regulatory_chunker"] = {"chunks": len(chunks)}

    evidence = [evidence_ref] if evidence_ref else (citations or [contract_terms.SOURCE_OF_RECORD])
    working = dict(record)
    working["evidence_ref"] = evidence[0] if evidence else ""
    judged, error = call("evidence_or_refuse", CAPABILITY_ID, working, tenant_id)
    if error:
        return {
            "ok": False,
            "error": "clause %s carries no evidence: %s" % (clause_id, error),
            "capability_id": CAPABILITY_ID,
        }
    allowed = bool(judged.get("allowed"))
    blocks["evidence_or_refuse"] = {"allowed": allowed, "claims": judged.get("verdicts") or []}

    request, error = call("governance_gate", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    gate_request = request.get("request") if isinstance(request.get("request"), dict) else {}
    blocks["governance_gate"] = {
        "request_id": gate_request.get("id"),
        "status": gate_request.get("status"),
    }

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "clause_id": clause_id,
        "clause_type": clause_type,
        "source_text": str(record.get("source_text") or ""),
        "evidence_ref": working.get("evidence_ref") or "",
        "governance_state": "requested",
    }
    computed = {
        "clause_id": clause_id,
        "clause_type": clause_type,
        "cited_evidence": stored["evidence_ref"],
        "citations": citations,
        "chunks": len(chunks),
        "evidence_allowed": allowed,
        "governance_request_id": gate_request.get("id"),
        "governance_state": "requested",
        "requires_approval": True,
        "approval_note": (
            "adoption of this clause needs an approved governance request; "
            "the gate refuses any action without one"
        ),
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("documents"),
    }
