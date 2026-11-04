"""Performance security and retention ledger, with its lifecycle state."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app import contract_terms, formulas
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "payment_security_and_retention_ledger"
ENTITY = "payment_security_and_retention_ledger"
BLOCK_IDS = ["finance_canonical_model", "transaction_state_machine", "audit_chain"]


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    entry_type = str(record.get("entry_type") or "performance_security")
    lifecycle_state = str(record.get("lifecycle_state") or "created")
    contract_amount = float(record.get("accepted_contract_amount") or 0.0)
    ps_rate = float(record.get("performance_security_rate") or contract_terms.performance_security_rate())
    retention_rate = float(record.get("retention_rate") or contract_terms.retention_rate())
    ps_rate = min(max(ps_rate, 0.0), 1.0)
    retention_rate = min(max(retention_rate, 0.0), 1.0)

    security = formulas.rate_applied(contract_amount, ps_rate)
    retention = formulas.rate_applied(contract_amount, retention_rate)
    release_share = contract_terms.retention_release_at_taking_over()
    release = formulas.rate_applied(float(retention["value"]), release_share)

    stated = float(record.get("amount_held") or 0.0)
    if stated > 0:
        held = round(stated, 2)
        held_source = "stated by the caller"
    elif entry_type == "performance_security":
        held = round(float(security["value"]), 2)
        held_source = security["address"]
    elif entry_type == "retention":
        held = round(float(retention["value"]), 2)
        held_source = retention["address"]
    else:
        held = round(float(release["value"]), 2)
        held_source = release["address"]

    working = dict(record)
    working["amount_held"] = held
    working["currency"] = str(record.get("currency") or "")

    blocks: Dict[str, Any] = {}

    normalized, error = call("finance_canonical_model", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    issues = normalized.get("issues") or []
    blocks["finance_canonical_model"] = {
        "record_type": normalized.get("record_type"),
        "issues": issues,
        "digest": normalized.get("record_digest"),
    }

    lifecycle, error = call("transaction_state_machine", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["transaction_state_machine"] = {
        "state": lifecycle.get("current_state"),
        "allowed_events": lifecycle.get("allowed_events") or [],
        "terminal": bool(lifecycle.get("terminal")),
    }

    chained, error = call("audit_chain", CAPABILITY_ID, working, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    chain = chained.get("record") if isinstance(chained.get("record"), dict) else {}
    blocks["audit_chain"] = {"evidence_id": chain.get("id")}

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "entry_type": entry_type,
        "accepted_contract_amount": contract_amount,
        "performance_security_rate": ps_rate,
        "retention_rate": retention_rate,
        "amount_held": held,
        "lifecycle_state": str(lifecycle.get("current_state") or lifecycle_state),
    }
    computed = {
        "entry_type": entry_type,
        "performance_security": round(float(security["value"]), 2),
        "security_formula": security["address"],
        "retention": round(float(retention["value"]), 2),
        "retention_formula": retention["address"],
        "release_at_taking_over": round(float(release["value"]), 2),
        "release_formula": release["address"],
        "amount_held": held,
        "amount_source": held_source,
        "lifecycle_state": stored["lifecycle_state"],
        "allowed_events": blocks["transaction_state_machine"]["allowed_events"],
        "evidence_id": chain.get("id"),
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("formulas"),
    }
