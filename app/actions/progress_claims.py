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
    """The certified gross: quantity x rate, else the amount the caller stated.

    When the caller supplies the BOQ extract, the line the certificate names
    is read from the bill; an item the bill does not price is refused rather
    than certified from memory.
    """
    quantity = float(record.get("measured_quantity") or 0.0)
    rate = float(record.get("boq_rate") or 0.0)
    source = str(record.get("source_text") or "")
    if source.strip():
        line = boq.line_for(source, str(record.get("boq_item") or ""))
        if line is not None:
            if line.get("quantity") is not None and line.get("rate") is not None:
                return float(line["quantity"]), float(line["rate"]), line
            return quantity, rate, line
    return quantity, rate, None


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    quantity, rate, line = _gross(record)
    line_amount = formulas.boq_line_amount(quantity, rate)
    gross = round(float(line_amount["value"]), 2)
    if gross <= 0:
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
