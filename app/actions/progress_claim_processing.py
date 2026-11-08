"""Interim Payment Certificates assessed against the BOQ.

Measured quantities are priced at the BOQ rate, retention is taken at the
Clause 14.3 rate, and every figure is cited back to the BOQ item and clause.
"""

from __future__ import annotations

from app import contract_terms as terms
from app import formulas
from app.actions._support import (
    add_days, as_float, block_result, check, input_digest, iso, ok, as_date,
    require_payload, round_money, tenant_id,
)
from app.block_inputs import default_block_action, ensure_boq_csv
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "progress_claim_processing"
ENTITY = "progress_claim_processing"
BLOCK_IDS = [
    "boq_processor",
    "finance_canonical_model",
    "finance_reconciliation_workflow",
    "approval_rules",
    "document_engine",
]
BLOCK_DEFAULT_ACTIONS = {
    block: default_block_action(block) for block in BLOCK_IDS
}

SCOPE_READS = ["payload", "app.contract_terms", "store:boq_basis.csv"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]


def _claim_items(payload):
    """The BOQ items this certificate measures: one item, else the whole bill."""
    chosen = terms.boq_item(str(payload.get("boq_item") or ""))
    if chosen is not None:
        return [chosen]
    return [dict(item) for item in terms.BOQ_ITEMS]


def _certified_amount(payload, items, boq_result):
    stated = as_float(payload.get("certified_amount"))
    if stated > 0:
        return stated
    measured = as_float(payload.get("measured_quantity"))
    rate = as_float(payload.get("boq_rate"))
    if measured > 0 and rate > 0:
        return measured * rate
    if len(items) == 1:
        return float(items[0]["qty"]) * float(items[0]["rate"])
    total = as_float(block_result(boq_result).get("total_cost"))
    return total or terms.ACCEPTED_CONTRACT_AMOUNT


def handle(payload):
    payload = require_payload(payload)
    items = _claim_items(payload)
    period = iso(as_date(payload.get("claim_period")))
    taking_over = as_date(payload.get("taking_over_date"))
    declared_defects_end = payload.get("defects_end_date")
    defects_end = (
        as_date(declared_defects_end)
        if declared_defects_end
        else add_days(taking_over, terms.DEFECTS_NOTIFICATION_DAYS)
    )

    boq_answer = execute(
        "boq_processor",
        {"file_path": ensure_boq_csv(items), "currency": terms.currency_label()},
        action=BLOCK_DEFAULT_ACTIONS.get("boq_processor"),
    )
    stopped = check("boq_processor", boq_answer)
    if stopped:
        return stopped
    boq = block_result(boq_answer)
    line_items = list(boq.get("line_items") or [])

    certified = round_money(_certified_amount(payload, items, boq_answer))
    canonical_answer = execute(
        "finance_canonical_model",
        {
            "operation": "normalize_record",
            "record_type": "project_cost",
            "record": {
                "record_id": str(payload.get("claim_number") or payload.get("reference") or "claim"),
                "project_id": "harbourline-civil-works",
                "entity_id": "harbourline",
                "period": period[:7],
                "currency": terms.currency_label(),
                "amount": certified,
                "contract_id": terms.CONTRACT_FILENAME,
            },
        },
        action=BLOCK_DEFAULT_ACTIONS.get("finance_canonical_model"),
    )
    stopped = check("finance_canonical_model", canonical_answer)
    if stopped:
        return stopped
    canonical = block_result(canonical_answer)

    run_answer = execute(
        "finance_reconciliation_workflow",
        {
            "tenant_id": tenant_id(),
            "project_id": "harbourline-civil-works",
            "run_type": "actuals_vs_budget",
            "source_period": period[:7],
        },
        action=BLOCK_DEFAULT_ACTIONS.get("finance_reconciliation_workflow"),
    )
    stopped = check("finance_reconciliation_workflow", run_answer)
    if stopped:
        return stopped
    run = block_result(run_answer).get("run") or {}

    citation = terms.clause_citation(terms.RETENTION)
    approval_answer = execute(
        "approval_rules",
        {
            "project_id": "harbourline-civil-works",
            "source_doc": citation,
            "extracted": [
                {
                    "rule": "retention at %s of each certificate" % terms.RETENTION_RATIO,
                    "clause": terms.RETENTION,
                    "source": citation,
                }
            ],
        },
        action=BLOCK_DEFAULT_ACTIONS.get("approval_rules"),
    )
    stopped = check("approval_rules", approval_answer)
    if stopped:
        return stopped
    candidates = list(block_result(approval_answer).get("candidates") or [])

    narrative = (
        "Interim Payment Certificate %s for period %s. Measured BOQ items: %s. "
        "Certified amount %s %s. Retention per %s."
        % (
            payload.get("claim_number") or payload.get("reference") or "un-numbered",
            period,
            ", ".join(str(item.get("item_key") or item.get("item")) for item in line_items) or "none",
            certified,
            terms.currency_label(),
            citation,
        )
    )
    document_answer = execute(
        "document_engine",
        {"text": narrative},
        action=BLOCK_DEFAULT_ACTIONS.get("document_engine"),
    )
    stopped = check("document_engine", document_answer)
    if stopped:
        return stopped
    document = block_result(document_answer)

    retention = formulas.retention(certified)
    retention_value = round_money(retention["value"])
    release_at_taking_over = round_money(
        retention_value * terms.RETENTION_RELEASE_AT_TAKING_OVER
    )
    release_at_defects_end = round_money(
        retention_value * terms.RETENTION_RELEASE_AT_DEFECTS_END
    )
    net_payable = round_money(certified - retention_value)

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "certified_amount": certified,
            "currency": terms.currency_label(),
            "retention_rate": retention["rate"],
            "retention_amount": retention_value,
            "retention_release_at_taking_over": release_at_taking_over,
            "retention_release_at_defects_end": release_at_defects_end,
            "taking_over_date": iso(taking_over),
            "defects_end_date": iso(defects_end),
            "net_payable": net_payable,
            "boq_item_count": len(line_items),
            "boq_total_cost": round_money(as_float(boq.get("total_cost"))),
            "canonical_record_digest": canonical.get("record_digest"),
            "reconciliation_run": run.get("id"),
            "reconciliation_status": run.get("status"),
            "pending_approvals": len(candidates),
            "document_requirements": len(document.get("requirements") or []),
            "input_digest": input_digest(payload),
            "citations": [
                terms.clause_citation(terms.RETENTION),
                terms.boq_citation(items[0]["item"]) if len(items) == 1 else terms.document_citation(terms.BOQ_FILENAME),
            ],
            "authority": "documents (layer 2, precedence.v1)",
        }
    )
