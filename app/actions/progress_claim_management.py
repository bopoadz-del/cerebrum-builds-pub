"""progress_claim_management -- interim payment certificates against BOQ lines.

A claim is measured against one uploaded BOQ line, retention is withheld at
the contract's own percentage (Clause 14.3), the performance security is
derived from the Accepted Contract Amount (Clause 4.2), a reconciliation run
is opened for the period, the retention rule is submitted to the approval
register, and the certification is written to the audit ledger.

READS   the request record, the uploaded contract and BOQ source of record,
        the tenant's earlier claims for the cumulative position.
WRITES  evidence artifacts under STORAGE_PATH/workspace; the ROUTE persists
        the claim, never this handler.
NEVER   invents a BOQ rate, a retention percentage or a certified amount: a
        missing rate is read from document:harbourline_boq.xlsx and a missing
        percentage from document:harbourline_contract.pdf.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_data, formulas, store
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "progress_claim_management"
ENTITY = "progress_claim_management"
BLOCK_IDS = ["boq_processor", "finance_reconciliation_workflow", "approval_rules", "audit"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}


def _candidate_pending(answer: Any, rule_id: str) -> bool:
    """True when the approval register's answer lists this candidate pending.

    The register keeps a candidate inert until a named reviewer decides it;
    a candidate that is absent from the answer was not registered at all, so
    this reads the answer rather than assuming the ingest worked.
    """
    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            if (
                str(node.get("rule_id") or "") == rule_id
                and str(node.get("status") or "") == "pending_approval"
            ):
                return True
            return any(walk(value) for value in node.values())
        if isinstance(node, (list, tuple)):
            return any(walk(value) for value in node)
        return False

    return walk(answer)


def _row_gross(row: Dict[str, Any]) -> float:
    """A stored claim's gross amount, derived from the BOQ line when absent."""
    gross = _support.number_of(row, "gross_amount", 0.0)
    if gross > 0:
        return gross
    quantity = _support.number_of(row, "claimed_quantity", 0.0)
    rate = _support.number_of(row, "rate", 0.0)
    line = contract_data.boq_item(_support.text_of(row, "boq_item").upper())
    rate = rate or float((line or {}).get("rate") or 0.0)
    quantity = quantity or float((line or {}).get("quantity") or 0.0)
    return round(quantity * rate, 2)


def _prior_certified(tenant: str, reference: str) -> float:
    """The tenant's previously certified NET total, excluding this reference.

    Cumulative certification is one unit: every prior claim contributes what
    was actually certified after its own retention, never its gross. Mixing
    the two makes the claim's cumulative disagree with the dashboard's.
    """
    try:
        rows = store.list_all(CAPABILITY_ID, tenant_id=tenant)
    except Exception:  # noqa: BLE001 - a first run has no table yet
        return 0.0
    total = 0.0
    for row in rows:
        if str(row.get("reference") or "") == reference:
            continue
        gross = _row_gross(row)
        pct = _support.number_of(row, "retention_pct", 0.0) or contract_data.RETENTION_PCT
        total += formulas.certified_amount(gross, formulas.retention_amount(gross, pct))
    return round(total, 2)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "contract-administrator"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"

    item_code = _support.text_of(record, "boq_item").upper()
    line = contract_data.boq_item(item_code) if item_code else None
    if item_code and line is None:
        return refuse(
            f"BOQ item {item_code!r} is not in document:{contract_data.BOQ_DOCUMENT}",
            error_kind="unknown_boq_item",
            input_digest=input_digest,
        )

    description = _support.text_of(record, "description") or str((line or {}).get("description") or "")
    unit = str((line or {}).get("unit") or "")
    claimed_quantity = _support.number_of(record, "claimed_quantity", 0.0)
    rate = _support.number_of(record, "rate", 0.0) or float((line or {}).get("rate") or 0.0)
    boq_quantity = float((line or {}).get("quantity") or 0.0)
    if claimed_quantity > 0:
        quantity_source = "stated"
    elif line:
        # Measuring the whole line is what a claim without a quantity would
        # otherwise do silently: state it, and let the certificate say so.
        claimed_quantity = boq_quantity
        quantity_source = "whole_boq_line"
    else:
        quantity_source = "not_stated"
    gross = _support.number_of(record, "gross_amount", 0.0)
    if gross <= 0:
        gross = round(claimed_quantity * rate, 2)

    accepted = _support.number_of(record, "accepted_contract_amount", 0.0) or contract_data.boq_total()
    retention_pct = _support.number_of(record, "retention_pct", 0.0) or contract_data.RETENTION_PCT

    # The uploaded documents are the source of record. A caller figure that
    # departs from them is recorded as a divergence, with the document
    # winning -- the same precedence the contract-terms capability states.
    divergences: List[Dict[str, Any]] = []
    line_rate = float((line or {}).get("rate") or 0.0)
    stated_rate = _support.number_of(record, "rate", 0.0)
    if stated_rate and line_rate and abs(stated_rate - line_rate) > 1e-9:
        divergences.append(
            {
                "term": "boq_rate",
                "contract_value": line_rate,
                "caller_value": stated_rate,
                "winner": "documents",
                "loser": "caller",
            }
        )
    stated_retention = _support.number_of(record, "retention_pct", 0.0)
    if stated_retention and abs(stated_retention - contract_data.RETENTION_PCT) > 1e-9:
        divergences.append(
            {
                "term": "retention_pct",
                "contract_value": contract_data.RETENTION_PCT,
                "caller_value": stated_retention,
                "winner": "documents",
                "loser": "caller",
            }
        )
    stated_accepted = _support.number_of(record, "accepted_contract_amount", 0.0)
    if stated_accepted and abs(stated_accepted - contract_data.boq_total()) > 1e-9:
        divergences.append(
            {
                "term": "accepted_contract_amount",
                "contract_value": contract_data.boq_total(),
                "caller_value": stated_accepted,
                "winner": "documents",
                "loser": "caller",
            }
        )
    retention = formulas.retention_amount(gross, retention_pct)
    security = formulas.performance_security_amount(
        accepted, contract_data.PERFORMANCE_SECURITY_PCT
    )
    net = formulas.certified_amount(gross, retention)
    certified = gross > 0
    prior = _prior_certified(tenant, reference)
    cumulative = round(prior + net, 2)
    period = _support.text_of(record, "period") or "current"

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    boq_csv = contract_data.write_boq_csv(workspace, f"boq_{stem}")

    assessment = {
        "reference": reference,
        "boq_item": item_code or None,
        "description": description,
        "unit": unit,
        "period": period,
        "ipc_number": _support.text_of(record, "ipc_number") or f"IPC-{stem[:8]}",
        "claimed_quantity": claimed_quantity,
        "rate": rate,
        "gross_amount": gross,
        "accepted_contract_amount": accepted,
        "retention_pct": retention_pct,
        "retention_amount": retention,
        "performance_security_pct": contract_data.PERFORMANCE_SECURITY_PCT,
        "performance_security_amount": security,
        "net_certified": net,
        "prior_certified": prior,
        "cumulative_certified": cumulative,
        "currency": contract_data.currency_label(),
        "clauses": {
            "retention": contract_data.clause_number("retention"),
            "performance_security": contract_data.clause_number("performance_security"),
        },
        "boq_quantity": boq_quantity or None,
        "quantity_source": quantity_source,
        "certified": certified,
        "needs_measurement": not certified,
        # A claim measured beyond the BOQ line is reported, not silently
        # certified: the excess needs a variation the contract does not
        # provide for here.
        "quantity_exceeds_boq": bool(boq_quantity and claimed_quantity > boq_quantity),
        "divergences": divergences,
        "approval_rule_id": f"claim:{reference}",
        "approval_status": "pending_approval",
        "cumulative_exceeds_contract": cumulative > accepted,
        "citations": [contract_data.CONTRACT_DOCUMENT, contract_data.BOQ_DOCUMENT],
        "formula_authority": formulas.IMPROVISED,
        "authority": formulas.IMPROVISED,
    }

    inputs: Dict[str, Dict[str, Any]] = {
        "boq_processor": {
            "file_path": str(boq_csv),
            "currency": contract_data.currency_label(),
        },
        "finance_reconciliation_workflow": {
            "tenant_id": tenant,
            "project_id": contract_data.CONTRACT_DOCUMENT,
            "run_type": "actuals_vs_budget",
            "source_period": period,
            "created_by": principal,
        },
        # The claim itself enters the approval register as a candidate: it is
        # inert until a named reviewer decides it, one claim at a time.
        "approval_rules": {
            "project_id": tenant,
            "source_doc": contract_data.CONTRACT_DOCUMENT,
            "extracted": [
                {
                    "rule_id": f"claim:{reference}",
                    "text": (
                        f"Interim payment certificate {assessment['ipc_number']} for BOQ item "
                        f"{item_code or 'unstated'} is certified at {net} {assessment['currency']} "
                        f"after {retention_pct}% retention under Clause "
                        f"{contract_data.clause_number('retention')}."
                    ),
                    "ipc_number": assessment["ipc_number"],
                    "boq_item": item_code or None,
                    "claimed_quantity": claimed_quantity,
                    "gross_amount": gross,
                    "retention_pct": retention_pct,
                    "retention_amount": retention,
                    "net_certified": net,
                    "accepted_contract_amount": accepted,
                    "period": period,
                }
            ],
        },
        "audit": {
            "tenant_id": tenant,
            "project_id": contract_data.CONTRACT_DOCUMENT,
            "principal_id": principal,
            "action_name": "ipc_certified" if certified else "ipc_measurement_recorded",
            "resource_type": CAPABILITY_ID,
            "resource_id": reference,
            "status": "ok",
            "details": {
                "gross_amount": gross,
                "retention_amount": retention,
                "net_certified": net,
            },
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    artifact = _support.artifact_name("claim", assessment)
    _support.write_artifact(workspace, artifact, assessment)
    result = {
        **assessment,
        "certificate_file": artifact,
        "block_evidence": {
            "boq_parsed": isinstance(answers.get("boq_processor"), dict)
            and answers["boq_processor"].get("ok") is not False,
            "reconciliation_opened": isinstance(
                answers.get("finance_reconciliation_workflow"), dict
            )
            and answers["finance_reconciliation_workflow"].get("ok") is not False,
            # The claim is routable only when the register holds it pending;
            # an approval block that did not ingest the candidate is reported,
            # never assumed.
            "approval_registered": (
                isinstance(answers.get("approval_rules"), dict)
                and answers["approval_rules"].get("ok") is not False
                and _candidate_pending(answers.get("approval_rules"), assessment["approval_rule_id"])
            ),
            "audited": isinstance(answers.get("audit"), dict)
            and answers["audit"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
