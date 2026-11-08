"""claim_review_and_dispute_resolution -- reviewed claims and determinations.

Reviews a submitted claim against the source of record, records the disputed
item and the basis of the determination, and keeps an evidence trail. A
determination above the claimed value, or a decided claim with no stated
basis, is refused rather than recorded; an undecided review stays pending.

READS   the request record, the uploaded contract and BOQ.
WRITES  the review file under STORAGE_PATH/workspace; the ROUTE persists the
        review record, never this handler.
NEVER   decides a claim without a basis, or awards more than was claimed.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_data
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "claim_review_and_dispute_resolution"
ENTITY = "claim_review_and_dispute_resolution"
BLOCK_IDS = ["review", "dispute_resolution", "evidence_or_refuse", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

DETERMINATIONS = ("accepted", "reduced", "rejected", "pending")
CLAIMANT = "contract-administrator"
COUNTERPARTY = "contractor"


def _resolve_values(record: Dict[str, Any], claimed: float) -> tuple[float | None, str]:
    determination = (_support.text_of(record, "determination") or "pending").lower()
    stated = record.get("determined_value")
    determined = None
    if stated not in (None, ""):
        determined = _support.number_of(record, "determined_value", 0.0)
    elif determination == "accepted":
        determined = claimed
    elif determination == "rejected":
        determined = 0.0
    elif determination == "reduced":
        determined = None
    return determined, determination


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    claim_reference = _support.text_of(record, "claim_reference") or reference
    disputed_item = _support.text_of(record, "disputed_item") or "measured quantity"
    claimed = _support.number_of(record, "claimed_value", 0.0)
    basis = _support.text_of(record, "basis")
    determination = (_support.text_of(record, "determination") or "pending").lower()
    if determination not in DETERMINATIONS:
        return refuse(
            "determination must be one of: " + ", ".join(DETERMINATIONS),
            error_kind="invalid_determination",
            input_digest=input_digest,
        )

    determined, determination = _resolve_values(record, claimed)
    if determination == "reduced" and determined is None:
        return refuse(
            "a reduced determination must state the value it is reduced to",
            error_kind="missing_determined_value",
            input_digest=input_digest,
        )
    if determined is not None and determined > claimed:
        return refuse(
            "a determination cannot award more than the claim's claimed value",
            error_kind="determination_exceeds_claim",
            input_digest=input_digest,
        )
    stated = record.get("determined_value")
    if stated not in (None, ""):
        if determination == "accepted" and abs(determined - claimed) > 1e-9:
            return refuse(
                "an accepted determination awards the claimed value; record a reduced determination to award less",
                error_kind="determination_contradicts_value",
                input_digest=input_digest,
            )
        if determination == "rejected" and determined not in (None, 0.0):
            return refuse(
                "a rejected determination awards nothing; set the determined value to 0",
                error_kind="determination_contradicts_value",
                input_digest=input_digest,
            )
        if determination == "reduced" and determined >= claimed:
            return refuse(
                "a reduced determination must award less than the claimed value",
                error_kind="determination_contradicts_value",
                input_digest=input_digest,
            )
    if determination != "pending" and not basis:
        return refuse(
            "a decided claim must state the basis of its determination",
            error_kind="missing_basis",
            input_digest=input_digest,
        )

    reviewer = _support.text_of(record, "reviewer") or CLAIMANT
    principal = _support.text_of(record, "_principal_id", "principal_id") or reviewer
    evidence_ref = _support.text_of(record, "evidence_ref") or contract_data.CONTRACT_DOCUMENT
    review = {
        "reference": reference,
        "claim_reference": claim_reference,
        "disputed_item": disputed_item,
        "claimed_value": claimed,
        "determined_value": determined,
        "determination": determination,
        "basis": basis or "review opened; determination pending",
        "reviewer": reviewer,
        "evidence_ref": evidence_ref,
        "citation": contract_data.BOQ_DOCUMENT,
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    _support.write_artifact(workspace, f"review_{stem}.json", review)
    claims: List[Dict[str, Any]] = [
        {"id": claim_reference, "evidence": [evidence_ref]}
    ]
    inputs: Dict[str, Dict[str, Any]] = {
        "review": {
            "block_id": claim_reference,
            "user_id": reviewer,
            "rating": 3,
            "review_text": basis or f"Review of {disputed_item}",
            "limit": 10,
        },
        "dispute_resolution": {
            "dispute_id": f"review-{reference}",
            "task_id": claim_reference,
            "claimant": CLAIMANT,
            "claim_type": disputed_item,
            "parties": [CLAIMANT, COUNTERPARTY],
            "step": 0,
        },
        "evidence_or_refuse": {"claims": claims},
        "audit_chain": {
            "tenant_id": _support.text_of(record, "_tenant_id") or "local",
            "action_execution_id": f"review-{stem}",
            "action_type": "claim_reviewed",
            "principal_id": principal,
            "payload": review,
            "result": {"determination": determination, "determined_value": determined},
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"review": "get_reviews", "dispute_resolution": "open"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    result = {
        **review,
        "review_file": _support.artifact_name("review", review),
        "block_evidence": {
            "review_lookup": isinstance(answers.get("review"), dict)
            and answers["review"].get("ok") is not False,
            "dispute_opened": isinstance(answers.get("dispute_resolution"), dict)
            and answers["dispute_resolution"].get("ok") is not False,
            "evidence_checked": isinstance(answers.get("evidence_or_refuse"), dict)
            and answers["evidence_or_refuse"].get("ok") is not False,
            "chained": isinstance(answers.get("audit_chain"), dict)
            and answers["audit_chain"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 2 documents",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
