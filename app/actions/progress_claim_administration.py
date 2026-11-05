"""progress_claim_administration -- interim payment certificate preparation.

READS  caller payload (claim reference, quantities, status) and the uploaded
       contract/BOQ source of record.
WRITES the capability response envelope only; the HTTP route persists the
       request record under the caller's tenant.
NEVER  writes to the store, invents contract terms, or reports success over a
       block refusal.
"""

from __future__ import annotations

from app import formulas
from app.authority import authority_label
from app.block_inputs import (
    approval_inputs,
    block_action,
    boq_csv_path,
    claim_lines,
    cleanup_path,
    contract_citation,
    finance_inputs,
    prepare_block_input,
)
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "progress_claim_administration"
ENTITY = "progress_claim_administration"
BLOCK_IDS = ["boq_processor", "finance_reconciliation", "approval_rules"]

FAILED_STATUSES = {"error", "failed", "refused", "validation_error"}


def _refused(block_id, answer):
    return {
        "ok": False,
        "error": str(block_id) + ": " + str((answer or {}).get("error") or "block refused"),
        "block": block_id,
        "record": None,
        "id": None,
    }


def _accepted(answer) -> bool:
    return isinstance(answer, dict) and str(answer.get("status") or "").lower() not in FAILED_STATUSES


def handle(payload: dict) -> dict:
    data = dict(payload or {})
    reference = str(data.get("reference") or "IPC-DRAFT")
    currency = formulas.currency()
    lines = claim_lines(data)
    claimed = formulas.money(sum(line["amount"] for line in lines))
    if formulas.finite_number(data.get("claimed_amount"), 0.0) > 0:
        claimed = formulas.finite_number(data.get("claimed_amount"), claimed)
    certified = formulas.finite_number(data.get("certified_amount"), claimed)
    retention = formulas.retention_amount(certified)
    accepted_contract_amount = formulas.finite_number(data.get("accepted_contract_amount"), formulas.boq_total())
    security = formulas.performance_security(accepted_contract_amount)

    csv_path = boq_csv_path()
    try:
        boq_answer = execute(
            "boq_processor",
            {"file_path": csv_path, "currency": currency},
            action=block_action("boq_processor"),
        )
    except Exception as exc:  # noqa: BLE001 -- a block failure is a refusal
        return _refused("boq_processor", {"error": f"{type(exc).__name__}: {exc}"})
    finally:
        cleanup_path(csv_path)
    if not _accepted(boq_answer):
        return _refused("boq_processor", boq_answer)

    try:
        reconciliation = execute(
            "finance_reconciliation",
            finance_inputs(data),
            action=block_action("finance_reconciliation"),
        )
    except Exception as exc:  # noqa: BLE001
        return _refused("finance_reconciliation", {"error": f"{type(exc).__name__}: {exc}"})
    if not _accepted(reconciliation):
        return _refused("finance_reconciliation", reconciliation)

    try:
        approval = execute(
            "approval_rules",
            approval_inputs(data),
            action=block_action("approval_rules"),
        )
    except Exception as exc:  # noqa: BLE001
        return _refused("approval_rules", {"error": f"{type(exc).__name__}: {exc}"})
    if not _accepted(approval):
        return _refused("approval_rules", approval)

    exceptions = int(reconciliation.get("exception_count") or 0)
    record = {
        "id": None,
        "reference": reference,
        "status": str(data.get("status") or "open"),
        "claim_number": str(data.get("claim_number") or "IPC-" + reference),
        "period_from": data.get("period_from"),
        "period_to": data.get("period_to"),
        "boq_item_codes": ",".join(line["item"] for line in lines),
        "claimed_quantity": round(sum(float(line["qty"]) for line in lines), 4),
        "unit_rate": 0.0,
        "claimed_amount": formulas.money(claimed),
        "certified_amount": formulas.money(certified),
        "retention_amount": retention,
        "performance_security": security,
        "accepted_contract_amount": formulas.money(accepted_contract_amount),
        "line_items": lines,
        "clause_reference": "14.3, 4.2",
    }
    return {
        "ok": True,
        "record": record,
        "id": None,
        "currency": currency,
        "boq_total": formulas.boq_total(),
        "item_count": int(boq_answer.get("item_count") or len(lines)),
        "reconciliation": {
            "status": reconciliation.get("reconciliation_status"),
            "exception_count": exceptions,
            "matched": len(reconciliation.get("matched") or []),
        },
        "approval_candidates": len((approval.get("result") or {}).get("candidates") or []),
        "authority": authority_label(
            "source_of_record",
            detail="BOQ " + contract_citation() + " and Clause 14.3 / 4.2",
        ),
    }
