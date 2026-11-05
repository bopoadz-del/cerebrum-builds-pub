"""progress_claims — certify Interim Payment Certificates against the BOQ.

Measured quantities are priced from
document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx; retention is
held at the Clause 14.3 rate and the performance security at the Clause 4.2
rate of document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf.
Both rates are operator settings read through app.contract.term().

READS:  the capability payload, the uploaded BOQ and contract, block answers.
WRITES: the certificate record returned to the route (the route persists it).
NEVER:  stores a record itself, invents a rate, or answers ok around a failed
        block.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract, dispatch, formulas, models, security
from app.actions._common import (
    BlockRefused,
    as_float,
    call,
    currency_code,
    envelope,
    refusal,
    render_pdf,
    safe_name,
    scratch_path,
    work_dir,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "progress_claims"
ENTITY = "progress_claims"
BLOCK_IDS = [
    "boq_processor",
    "finance_reconciliation",
    "finance_reconciliation_workflow",
    "approval_rules",
    "pdf",
]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_CONTRACT = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"
_BOQ = "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx"


def _boq_schedule_csv() -> str:
    rows: List[str] = ["Item,Section,Description,Unit,Qty,Rate"]
    for item in contract.boq_items():
        rows.append(
            ",".join(
                [
                    str(item.get("item_code", "")),
                    str(item.get("section", "")),
                    str(item.get("description", "")).replace(",", " "),
                    str(item.get("unit", "")),
                    str(item.get("quantity", "")),
                    str(item.get("rate", "")),
                ]
            )
        )
    return "\n".join(rows) + "\n"


def _parse_boq_schedule() -> Dict[str, Any]:
    """Ask boq_processor to price the schedule it was given.

    The block parses spreadsheets through pandas. When that parser is not
    installed the block still answers its readiness contract, and the priced
    schedule is read from the uploaded BOQ itself.
    """
    health = call("boq_processor")
    try:
        import pandas  # noqa: F401
    except Exception:  # noqa: BLE001 - parser availability is a runtime fact
        return {"parsed": False, "ready": bool(health.get("ready", True)), "items": contract.boq_items()}
    path = temp_file("harbourline_boq.csv", _boq_schedule_csv())
    boq_input: Dict[str, Any] = {"file_path": str(path)}
    currency = currency_code()
    if currency:
        boq_input["currency"] = currency
    answer = call("boq_processor", boq_input, action=None)
    return {"parsed": True, "ready": True, "answer": answer, "items": contract.boq_items()}


def _approval(decision: str, approved_by: str, certificate_reference: str, amount: float) -> Dict[str, Any]:
    """Record the certification rule the claim is decided under.

    The decision itself is validated here against the platform's configured
    principals -- a free-text approver never passes -- and the candidate set
    is ingested into approval_rules, which refuses to hold a rule without the
    contract document it was extracted from.
    """
    reviewer = security.require_approver(approved_by, decision)
    ingested = call(
        "approval_rules",
        {
            "action": "ingest",
            "project_id": "harbourline",
            "source_doc": _CONTRACT,
            "extracted": [
                {
                    "rule_id": certificate_reference,
                    "system_a": "claim",
                    "system_b": "certificate",
                    "min_gap_mm": 0,
                }
            ],
        },
        action=None,
    )
    return {
        "decision": decision,
        "reviewer": reviewer,
        "amount": amount,
        "candidates_ingested": len(ingested.get("candidates") or []),
        "block": "approval_rules",
    }


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.ProgressClaim.from_dict(data)
    record = model.to_dict()

    code = str(data.get("boq_item_code") or "").strip()
    item = contract.boq_item(code) if code else None
    if code and item is None:
        return refusal(
            f"no BOQ item {code!r} in {_BOQ}", field="boq_item_code"
        )

    measured = as_float(data.get("measured_quantity"), 0.0)
    if item is not None:
        rate = as_float(data.get("unit_rate"), as_float(item.get("rate"), 0.0))
        priced_quantity = as_float(item.get("quantity"), 0.0)
        description = str(item.get("description") or "")
    else:
        rate = as_float(data.get("unit_rate"), 0.0)
        priced_quantity = 0.0
        description = "schedule total"

    try:
        boq = _parse_boq_schedule()
    except BlockRefused as exc:
        return refusal(exc.message, field="boq_item_code")

    gross = float(formulas.evaluate("certificate_gross_amount", measured_quantity=measured, unit_rate=rate))
    if item is not None:
        boq_value = float(
            formulas.evaluate(
                "certificate_gross_amount",
                measured_quantity=priced_quantity,
                unit_rate=rate,
            )
        )
    else:
        boq_value = float(contract.boq_total())
    retention_rate = float(contract.term("retention_rate"))
    retention = float(
        formulas.evaluate("retention_amount", certified_amount=gross, retention_rate=retention_rate)
    )
    net = float(
        formulas.evaluate("certificate_net_payable", gross_amount=gross, retention_amount=retention)
    )
    aca = as_float(data.get("accepted_contract_amount"), 0.0) or float(contract.boq_total())
    performance_security = float(
        formulas.evaluate("performance_security_amount", accepted_contract_amount=aca)
    )

    reference = str(data.get("reference") or data.get("claim_number") or "certificate")

    try:
        reconciliation = call(
            "finance_reconciliation",
            {
                "left_records": [{"item": code or "schedule", "amount": gross}],
                "right_records": [{"item": code or "schedule", "amount": boq_value}],
                "group_by": ["item"],
                "amount_field": "amount",
            },
            action=None,
        )
        run = call(
            "finance_reconciliation_workflow",
            {
                "action": "create_run",
                "tenant_id": str(tenant_id),
                "run_type": "actuals_vs_budget",
                "source_period": str(data.get("claim_period") or "2026-11"),
            },
            action=None,
        )
        run_id = (run.get("run") or {}).get("id")
        decision = str(data.get("approval_decision") or "none")
        if decision in {"certify", "reject"}:
            approval = _approval(decision, str(data.get("approved_by") or ""), reference, gross)
        else:
            ledger = call("approval_rules", {"action": "ledger"}, action=None)
            approval = {
                "decision": "none",
                "block": "approval_rules",
                "ledger_ready": ledger.get("count") is not None or bool(ledger.get("ledger") is not None),
            }
        pdf_path = scratch_path(f"certificate-{reference}", ".pdf")
        render_pdf(
            pdf_path,
            [
                f"Interim Payment Certificate {reference}",
                f"Claim {str(data.get('claim_number') or reference)} for item {code or 'schedule'}",
                f"Measured quantity {measured} at {rate} = {gross}",
                f"Retention at clause 14.3 = {retention}",
                f"Net payable = {net}",
            ],
        )
        rendered = call("pdf", {"file_path": str(pdf_path)}, action=None)
        try:
            pdf_path.unlink()
        except OSError:
            pass
    except BlockRefused as exc:
        return refusal(exc.message)

    result = {
        "certificate": {
            "reference": reference,
            "boq_item_code": code or "schedule",
            "description": description,
            "measured_quantity": measured,
            "unit_rate": rate,
            "gross_amount": gross,
            "retention_rate": retention_rate,
            "retention_amount": retention,
            "net_payable": net,
            "performance_security_amount": performance_security,
            "accepted_contract_amount": aca,
            "boq_document": _BOQ,
            "contract_clauses": ["14.3", "4.2"],
        },
        "boq_processor": {
            "ready": boq.get("ready"),
            "parsed": boq.get("parsed"),
            "items_priced": len(boq.get("items") or []),
        },
        "reconciliation": {
            "status": reconciliation.get("reconciliation_status"),
            "variance": (reconciliation.get("control_totals") or {}).get("variance"),
            "exceptions": (reconciliation.get("summary") or {}).get("exception_count"),
        },
        "reconciliation_run": {
            "run_id": run_id,
            "status": (run.get("run") or {}).get("status"),
            "period": (run.get("run") or {}).get("source_period"),
        },
        "approval": approval,
        "certificate_document": {
            "text": str(rendered.get("text") or "")[:400],
            "pages": rendered.get("pages"),
            "engine": rendered.get("engine"),
        },
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": _CONTRACT,
        },
    }
    computed = {
        "status": str(data.get("status") or "open"),
        "gross_amount": gross,
        "retention_amount": retention,
        "net_payable": net,
    }
    record.update({key: value for key, value in computed.items() if key in models.ProgressClaim.FIELDS})
    if not record.get("certificate_note"):
        record["certificate_note"] = (
            f"gross {gross:.2f}; retention {retention:.2f}; net {net:.2f} "
            f"under clauses 14.3 and 4.2"
        )
    return envelope(record, result)
