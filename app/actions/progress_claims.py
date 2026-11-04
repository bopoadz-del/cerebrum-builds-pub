"""Interim payment certificates: measured value, retention and approval route."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app import boq, contract_terms, formulas
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "progress_claims"
ENTITY = "progress_claims"
BLOCK_IDS = ["boq_processor", "formula_executor", "finance_reconciliation", "approval_rules", "pdf"]


def _gross(record: Dict[str, Any]) -> tuple:
    """(measured quantity, BOQ rate, bill line) for one certificate.

    The quantity certified is the work the caller measured, never the BOQ
    line's whole quantity: a bill quantity is the ceiling, not the progress.
    When the caller supplies the BOQ extract, the rate is read from the bill
    (a caller-entered rate cannot overwrite the source of record), an item the
    bill does not contain is refused, and a measurement beyond the bill's
    quantity is refused rather than certified from memory.
    """
    quantity = float(record.get("measured_quantity") or 0.0)
    rate = float(record.get("boq_rate") or 0.0)
    source = str(record.get("source_text") or "")
    item = str(record.get("boq_item") or "")
    if source.strip():
        line = boq.line_for(source, item)
        if line is None:
            # The bill is the source of record: a certificate cannot price a
            # line the uploaded BOQ does not contain.
            raise ValueError(
                "the BOQ extract contains no item %r to certify" % (item or "(unnamed)")
            )
        bill_quantity = line.get("quantity")
        bill_rate = line.get("rate")
        if bill_quantity is not None and quantity > float(bill_quantity) + 1e-9:
            raise ValueError(
                "measured quantity %s for item %s exceeds the BOQ quantity %s"
                % (quantity, item or "(unnamed)", bill_quantity)
            )
        if bill_rate is not None:
            rate = float(bill_rate)
        return quantity, rate, line
    return quantity, rate, None


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    try:
        quantity, rate, line = _gross(record)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "capability_id": CAPABILITY_ID}
    line_amount = formulas.boq_line_amount(quantity, rate)
    gross = round(float(line_amount["value"]), 2)
    if gross <= 0 and line is None:
        # Only an unpriced (manual) certificate may carry the caller's stated
        # amount; when the bill governs the line, zero measured work is zero.
        gross = round(float(record.get("amount_certified") or 0.0), 2)
    retention_rate = float(record.get("retention_rate") or contract_terms.retention_rate())
    retention_rate = min(max(retention_rate, 0.0), 1.0)
    retention = formulas.rate_applied(gross, retention_rate)
    held = round(float(retention["value"]), 2)
    net = formulas.net_certified(gross, held)
    approval_state = str(record.get("approval_state") or "pending")
    blocks: Dict[str, Any] = {}

    readiness, error = call("boq_processor", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["boq_processor"] = {"ready": bool(readiness.get("ready"))}

    priced, error = call("formula_executor", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["formula_executor"] = {
        "value": priced.get("execution_result"),
        "address": line_amount["address"],
    }

    working = dict(record)
    working["amount_certified"] = gross
    working["retention_held"] = held
    reconciliation, error = call("finance_reconciliation", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["finance_reconciliation"] = {
        "status": reconciliation.get("reconciliation_status"),
        "summary": reconciliation.get("summary"),
    }

    approval, error = call("approval_rules", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    candidates = approval.get("result") if isinstance(approval.get("result"), dict) else approval
    blocks["approval_rules"] = {
        "candidates": len((candidates or {}).get("candidates") or []),
    }

    certificate, error = call("pdf", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    certificate_text = str(certificate.get("text") or "")
    blocks["pdf"] = {
        "pages": certificate.get("pages"),
        "engine": certificate.get("engine"),
        "characters": len(certificate_text),
    }

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "ipc_number": str(record.get("ipc_number") or ""),
        "boq_item": str(record.get("boq_item") or ""),
        "measured_quantity": quantity,
        "boq_rate": rate,
        "retention_rate": retention_rate,
        "amount_certified": gross,
        "retention_held": held,
        "approval_state": approval_state,
    }
    computed = {
        "boq_item": stored["boq_item"],
        "boq_line": line,
        "boq_quantity": (line or {}).get("quantity"),
        "measured_quantity": quantity,
        "gross_measured": gross,
        "line_formula": line_amount["address"],
        "retention_held": held,
        "retention_formula": retention["address"],
        "net_certified": round(float(net["value"]), 2),
        "net_formula": net["address"],
        "approval_state": approval_state,
        "reconciled": blocks["finance_reconciliation"]["status"],
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("formulas"),
    }
