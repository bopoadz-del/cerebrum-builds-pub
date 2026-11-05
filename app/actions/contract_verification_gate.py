"""contract_verification_gate — ground every claim in the uploaded documents.

A claim, certificate or record is verified only when it cites a governing
clause of
document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf or a
priced item of
document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx. Anything
that cannot be grounded is flagged, and a claim submitted without evidence is
refused by the evidence block itself.

READS:  the capability payload, both uploaded documents, block answers.
WRITES: the verification record returned to the route (the route persists it).
NEVER:  verifies a claim against a document that was not uploaded, or answers
        ok around a failed block.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract, dispatch, models, retrieval
from app.actions._common import (
    BlockRefused,
    call,
    digest,
    envelope,
    refusal,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "contract_verification_gate"
ENTITY = "contract_verification_gate"
BLOCK_IDS = ["evidence_or_refuse", "governance_gate", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_CONTRACT = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"
_BOQ = "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx"


def _grounding(clause_ref: str, item_code: str) -> List[Dict[str, Any]]:
    grounds: List[Dict[str, Any]] = []
    if clause_ref:
        row = contract.clause(clause_ref)
        if row:
            grounds.append(
                {
                    "kind": "clause",
                    "ref": f"Clause {clause_ref}",
                    "source": _CONTRACT,
                    "text": f"{row.get('heading', '')}: {row.get('text', '')}",
                }
            )
    if item_code:
        item = contract.boq_item(item_code)
        if item:
            grounds.append(
                {
                    "kind": "boq_item",
                    "ref": str(item.get("item_code")),
                    "source": _BOQ,
                    "text": (
                        f"{item.get('description')} - {item.get('quantity')} "
                        f"{item.get('unit')} at {item.get('rate')}"
                    ),
                }
            )
    return grounds


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.ContractVerification.from_dict(data)
    record = model.to_dict()

    clause_ref = str(data.get("clause_ref") or "").strip()
    item_code = str(data.get("boq_item_code") or "").strip()
    if clause_ref and contract.clause(clause_ref) is None:
        return refusal(
            f"clause {clause_ref!r} is not in {_CONTRACT}", field="clause_ref"
        )
    if item_code and contract.boq_item(item_code) is None:
        return refusal(f"BOQ item {item_code!r} is not in {_BOQ}", field="boq_item_code")

    grounds = _grounding(clause_ref, item_code)
    subject = str(data.get("subject_reference") or data.get("reference") or "record")
    decision = str(data.get("decision") or "verify")
    claim_text = str(data.get("evidence") or "").strip()

    retrieved = None
    if not grounds and claim_text:
        hit = retrieval.best_grounding(claim_text)
        if hit is not None:
            retrieved = hit
            grounds = [
                {
                    "kind": str(hit.get("kind")),
                    "ref": str(hit.get("label")),
                    "source": str(hit.get("source")),
                    "text": str(hit.get("text")),
                }
            ]
    if decision == "verify" and not grounds:
        decision = "flag"

    claims = [
        {
            "id": subject,
            "claim": claim_text or f"{data.get('subject_type') or 'record'} {subject}",
            "evidence": [f"{row['source']} {row['ref']}" for row in grounds],
        }
    ]
    if not claims[0]["evidence"]:
        claims[0]["evidence"] = [f"{_CONTRACT} (no clause cited)"]

    try:
        judged = call("evidence_or_refuse", {"claims": claims}, action="judge")
        request = call(
            "governance_gate",
            {
                "action": "create_request",
                "tenant_id": str(tenant_id),
                "action_type": "contract_verification",
                "target_id": subject,
                "requester_id": "contract-administrator",
            },
            action=None,
        )
        chained = call(
            "audit_chain",
            {
                "action_execution_id": subject,
                "action_type": "contract_verification",
                "principal_id": "contract-administrator",
                "payload": {"clause_ref": clause_ref, "boq_item_code": item_code},
                "result": {"decision": decision, "grounds": len(grounds)},
            },
            action="record_evidence",
        )
    except BlockRefused as exc:
        return refusal(exc.message)

    verdicts = judged.get("verdicts") or []
    evidenced = bool(verdicts and verdicts[0].get("evidenced") and grounds)
    if decision == "verify" and not evidenced:
        return refusal(
            f"{subject} cannot be grounded in a governing clause or BOQ item",
            field="evidence",
        )

    body = {
        "verification": {
            "subject_type": data.get("subject_type") or "other",
            "subject_reference": subject,
            "clause_ref": clause_ref or None,
            "boq_item_code": item_code or None,
            "grounds": grounds,
            "decision": decision,
            "evidenced": evidenced,
            "evidence_text": claim_text or None,
        },
        "evidence_or_refuse": {
            "allowed": judged.get("allowed"),
            "verdicts": verdicts,
        },
        "governance": {
            "request_id": (request.get("request") or {}).get("id"),
            "status": (request.get("request") or {}).get("status"),
        },
        "retrieval": (
            {"passage": retrieved.get("label"), "score": retrieved.get("score")}
            if retrieved
            else None
        ),
        "chain": {
            "record_id": (chained.get("record") or {}).get("id"),
            "chain_hash": (chained.get("record") or {}).get("chain_hash"),
        },
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": grounds[0]["source"] if grounds else _CONTRACT,
            "divergences": [
                {"layer": "procedures", "source": _BOQ, "value": item_code}
                for item_code in ([item_code] if item_code and not grounds else [])
            ],
        },
    }
    record["decision"] = decision
    record["evidence"] = claim_text or (
        "; ".join(f"{row['source']} {row['ref']}" for row in grounds) or None
    )
    record["status"] = "closed" if decision == "verify" and evidenced else "in_progress"
    if not record.get("clause_ref") and clause_ref:
        record["clause_ref"] = clause_ref
    if not record.get("boq_item_code") and item_code:
        record["boq_item_code"] = item_code
    body["verification"]["evidence_digest"] = digest(claim_text or subject)
    return envelope(record, body)
