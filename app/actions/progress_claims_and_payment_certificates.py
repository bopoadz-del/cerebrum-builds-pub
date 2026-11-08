"""progress_claims_and_payment_certificates -- Interim Payment Certificates.

A claim measures a BOQ line by quantity at its BOQ rate, deducts retention
under Clause 14.3 and (for the first certificate) the performance-security
deduction under Clause 4.2, and reports the 50/50 release points. The
certificate is routed through the approval set and a prepared audit step, and
the remaining BOQ quantity is carried forward.

READS   the request record, the uploaded BOQ and the contract terms.
WRITES  the IPC summary and BOQ material under STORAGE_PATH/workspace; the
        ROUTE persists the claim, never this handler.
NEVER   certifies a BOQ item outside the uploaded BOQ, or pays a certificate
        without stating its retention.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_data, formulas, sources
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "progress_claims_and_payment_certificates"
ENTITY = "progress_claims_and_payment_certificates"
BLOCK_IDS = ["boq_processor", "approval_rules", "workflow", "finance_canonical_model", "billing", "audit"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

PROJECT_ID = sources.PROJECT_KEY


def _audit_step(step_id: str, reference: str, payload: Dict[str, Any], principal: str) -> Dict[str, Any]:
    """A fully prepared workflow child: action at step level and in params."""
    return {
        "id": step_id,
        "block": "audit",
        "action": "log",
        "params": {"action": "log"},
        "input": {
            "action_type": "ipc_certified",
            "principal_id": principal,
            "payload": payload,
            "result": {"reference": reference, "net_certified": payload.get("net_certified")},
            "topic": "progress_claim.certified",
            "message": f"Interim Payment Certificate {reference} certified",
            "channel": "mcp",
            "tool": "audit",
        },
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    item_code = _support.text_of(record, "boq_item").upper()

    lines = contract_data.boq_lines()
    if not lines:
        return refuse(
            "the uploaded BOQ carries no line items to certify against",
            error_kind="empty_boq",
            input_digest=input_digest,
        )
    line = contract_data.boq_item(item_code) if item_code else lines[0]
    if line is None:
        return refuse(
            f"boq_item {item_code!r} is not in the uploaded BOQ; known items: "
            + ", ".join(row["item"] for row in lines),
            error_kind="unknown_boq_item",
            input_digest=input_digest,
        )

    claimed = _support.number_of(record, "claimed_quantity", 0.0)
    # One measured quantity drives the certificate and the carried-forward
    # balance: a certificate for the whole line cannot also carry the whole
    # line forward as uncertified.
    measured = claimed if claimed > 0 else float(line["quantity"])
    gross = _support.number_of(record, "gross_amount", 0.0)
    if gross <= 0:
        gross = formulas.round_money(measured * float(line["rate"]))
    if gross < 0:
        return refuse(
            "a certificate cannot carry a negative gross amount",
            error_kind="invalid_amount",
            input_digest=input_digest,
        )

    retention_pct = _support.number_of(record, "retention_pct", contract_data.RETENTION_PCT)
    if retention_pct <= 0:
        retention_pct = contract_data.RETENTION_PCT
    retention_pct = max(0.0, min(retention_pct, 100.0))
    retention = formulas.retention_amount(gross, retention_pct)

    accepted = _support.number_of(record, "accepted_contract_amount", contract_data.boq_total())
    if accepted <= 0:
        accepted = contract_data.boq_total()

    ipc_number = _support.text_of(record, "ipc_number") or "1"
    # Clause 4.2 performance security is a security the contractor provides,
    # tracked against the Accepted Contract Amount; it is not a deduction from
    # an Interim Payment Certificate (retention under Clause 14.3 is).
    security = formulas.performance_security(accepted, contract_data.PERFORMANCE_SECURITY_PCT)
    net = formulas.net_certificate(gross, retention, 0.0)
    release = formulas.retention_release(
        retention, contract_data.RETENTION_RELEASE_SPLIT_PCT
    )
    carried = formulas.round_money(max(0.0, float(line["quantity"]) - measured))

    period = _support.text_of(record, "period") or "current"
    principal = _support.text_of(record, "_principal_id", "principal_id") or "contract-administrator"
    certificate = {
        "reference": reference,
        "ipc_number": ipc_number,
        "period": period,
        "boq_item": line["item"],
        "boq_description": line["description"],
        "claimed_quantity": measured,
        "carried_forward_quantity": carried,
        "gross_amount": gross,
        "retention_pct": retention_pct,
        "retention_amount": retention,
        "performance_security_amount": security,
        "performance_security_deducted": 0.0,
        "net_certified": net,
        "release_at_taking_over": release["at_taking_over"],
        "release_at_dnp_end": release["at_dnp_end"],
        "clauses": {
            "retention": contract_data.clause_number("retention"),
            "performance_security": contract_data.clause_number("performance_security"),
        },
        "citation": contract_data.BOQ_DOCUMENT,
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    try:
        boq_csv = contract_data.write_boq_csv(workspace, f"boq_{stem}")
    except OSError:
        boq_csv = None
    _support.write_artifact(workspace, f"ipc_{stem}.json", certificate)

    steps: List[Dict[str, Any]] = [
        _audit_step("step_0", reference, certificate, principal)
    ]
    inputs: Dict[str, Dict[str, Any]] = {
        "boq_processor": {"file_path": str(boq_csv) if boq_csv is not None else ""},
        "approval_rules": {
            "project_id": PROJECT_ID,
            "source_doc": contract_data.CONTRACT_DOCUMENT,
            "extracted": [
                {
                    "rule_id": f"retention:{reference}",
                    "text": "Retention is a percentage of each Interim Payment Certificate.",
                    "amount": retention,
                }
            ],
        },
        "workflow": {
            "pipeline_id": f"ipc-{stem}",
            "steps": steps,
            "result": {"step_0": steps[0]["input"]},
            "topic": "progress_claim.certified",
            "channel": "mcp",
            "tool": "workflow",
            "payload": certificate,
        },
        "finance_canonical_model": {
            "record_type": "invoice",
            "record": {
                "reference": reference,
                "amount": net,
                "currency": contract_data.currency_label(),
                "party": PROJECT_ID,
            },
        },
        "billing": {
            "api_key": _support.text_of(record, "_tenant_id") or "local",
            "user_id": principal,
            "block_id": "progress_claims_and_payment_certificates",
            "gross_amount": gross,
            "currency": contract_data.currency_label(),
        },
        "audit": {
            "action_type": "ipc_certified",
            "principal_id": principal,
            "action_name": "ipc_certified",
            "payload": certificate,
            "result": {"net_certified": net, "reference": reference},
            "reference": reference,
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"approval_rules": "ingest", "billing": "record_purchase", "workflow": "run"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    result = {
        **certificate,
        "accepted_contract_amount": accepted,
        "currency": contract_data.currency_label(),
        "certificate_file": _support.artifact_name("ipc", certificate),
        "approval": {
            "project_id": PROJECT_ID,
            "source_doc": contract_data.CONTRACT_DOCUMENT,
            "status": "ingested",
        },
        "block_evidence": {
            "boq_parsed": isinstance(answers.get("boq_processor"), dict)
            and answers["boq_processor"].get("ok") is not False,
            "approval_routed": isinstance(answers.get("approval_rules"), dict)
            and answers["approval_rules"].get("ok") is not False,
            "workflow_completed": isinstance(answers.get("workflow"), dict)
            and answers["workflow"].get("ok") is not False,
            "canonicalised": isinstance(answers.get("finance_canonical_model"), dict)
            and answers["finance_canonical_model"].get("ok") is not False,
            "billed": isinstance(answers.get("billing"), dict)
            and answers["billing"].get("ok") is not False,
            "audited": isinstance(answers.get("audit"), dict)
            and answers["audit"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 3 formulas",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
