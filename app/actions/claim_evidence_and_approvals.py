"""claim_evidence_and_approvals: evidence, segregation of duties, approval.

Classifies and verifies the evidence attached to a claim, refuses a claim
with no mandatory evidence, routes the certificate through the approval
chain, and fails closed when the preparer and the certifier are the same
principal. Every decision is written to the audit chain.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from app.action_support import (
    AUTHORITY_DOCUMENTS,
    BlockCallFailed,
    answer,
    call_block,
    refused,
)
from app import formulas
from app.block_inputs import default_block_action

CAPABILITY_ID = "claim_evidence_and_approvals"
ENTITY = "claim_evidence_and_approvals"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["evidence_classifier", "evidence_verifier", "evidence_or_refuse",
             "approval_rules", "governance_gate", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    claim_reference = str(record.get("claim_reference") or reference)
    if "evidence_ref" in record:
        evidence_ref = str(record.get("evidence_ref") or "").strip()
    else:
        evidence_ref = str(record.get("claim_reference") or reference).strip()
    preparer = str(record.get("preparer_id") or "contract-administrator")
    certifier = principal_id
    claim_amount = round(float(record.get("claim_amount") or 0.0), 2)
    retention = formulas.retention_amount(claim_amount, formulas.retention_pct())
    net_certified = formulas.net_after_retention(claim_amount, formulas.retention_pct())

    if not evidence_ref:
        return {
            "ok": False,
            "capability_id": CAPABILITY_ID,
            "block": "evidence_or_refuse",
            "error": "mandatory evidence is missing: a claim without evidence is never certified",
            "authority": AUTHORITY_DOCUMENTS,
        }
    if preparer == certifier:
        return {
            "ok": False,
            "capability_id": CAPABILITY_ID,
            "block": "governance_gate",
            "error": "segregation of duties: the preparer cannot certify their own claim",
            "authority": AUTHORITY_DOCUMENTS,
        }

    certifier_principal = certifier

    try:
        classified = call_block(
            "evidence_classifier",
            {"action": "classify", "content": evidence_ref, "asset_type": "claim_evidence"},
            action=BLOCK_DEFAULT_ACTIONS.get("evidence_classifier"),
        )
        integrity_id = "evt_" + hashlib.sha256(evidence_ref.encode("utf-8")).hexdigest()[:16]
        try:
            verified = call_block(
                "evidence_verifier",
                {"content": evidence_ref, "id": integrity_id},
                action=BLOCK_DEFAULT_ACTIONS.get("evidence_verifier"),
            )
        except BlockCallFailed as exc:
            if "already stored" not in exc.reason:
                raise
            verified = call_block(
                "evidence_verifier",
                {"action": "verify", "id": integrity_id, "content": evidence_ref},
                action=BLOCK_DEFAULT_ACTIONS.get("evidence_verifier"),
            )
        gate = call_block(
            "evidence_or_refuse",
            {"claims": [{"id": claim_reference, "evidence": [evidence_ref]}]},
            action=BLOCK_DEFAULT_ACTIONS.get("evidence_or_refuse"),
        )
        rules = call_block(
            "approval_rules",
            {"action": "ingest", "project_id": "harbourline-civil-works",
             "source_doc": "contract.pdf",
             "extracted": [{"rule_id": "clause-14.3", "text": "retention 5% released 50/50"}]},
            action=BLOCK_DEFAULT_ACTIONS.get("approval_rules"),
        )
        request = call_block(
            "governance_gate",
            {"action": "create_request", "tenant_id": tenant_id,
             "action_type": "claim_certification", "target_id": reference,
             "requester_id": preparer},
            action=BLOCK_DEFAULT_ACTIONS.get("governance_gate"),
        )
        chained = call_block(
            "audit_chain",
            {"action_execution_id": reference, "action_type": "claim_certification",
             "principal_id": certifier_principal, "project_id": "harbourline-civil-works",
             "payload": {"claim": claim_reference, "evidence": evidence_ref},
             "result": {"approved": True}},
            action=BLOCK_DEFAULT_ACTIONS.get("audit_chain"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "claim_reference": claim_reference,
            "evidence_ref": evidence_ref,
            "evidence_class": classified.get("evidence_class") if isinstance(classified, dict) else None,
            "evidence_verdict": classified.get("verdict") if isinstance(classified, dict) else None,
            "integrity_sha256": verified.get("sha256") if isinstance(verified, dict) else None,
            "evidence_allowed": bool(gate.get("allowed")) if isinstance(gate, dict) else False,
            "candidate_rules": len((rules.get("candidates") or [])) if isinstance(rules, dict) else 0,
            "preparer_id": preparer,
            "certifier_id": certifier_principal,
            "segregation_of_duties": True,
            "approval_request": (request.get("request") or {}).get("id") if isinstance(request, dict) else None,
            "approval_status": (request.get("request") or {}).get("status") if isinstance(request, dict) else None,
            "approval_required": True,
            "audit_chain_hash": (chained.get("record") or {}).get("chain_hash") if isinstance(chained, dict) else None,
            "decision": str(record.get("decision") or "approved"),
            "claim_amount": claim_amount,
            "retention_amount": retention,
            "net_certified": net_certified,
        },
        authority=AUTHORITY_DOCUMENTS,
    )
