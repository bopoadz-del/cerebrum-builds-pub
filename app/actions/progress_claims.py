"""progress_claims -- Interim Payment Certificates under Clauses 14.3 and 4.2.

A certificate values the BOQ line, deducts 5% retention (Clause 14.3) and the
performance-security amount (Clause 4.2, on the first certificate), and states
the 50/50 retention release points. The arithmetic is deterministic and every
figure is cited against the uploaded BOQ and contract excerpt.

READS   the request record, the uploaded BOQ data, and the contract clauses.
WRITES  a certificate summary under STORAGE_PATH/workspace and this
        capability's result; the ROUTE persists the record, never the handler.
NEVER   pays a certificate without retention, or invents a BOQ headline rate.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict

from app import contract_data, formulas
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "progress_claims"
ENTITY = "progress_claims"
BLOCK_IDS = [
    "finance_reconciliation",
    "finance_canonical_model",
    "boq_processor",
    "validation",
    "approval_rules",
    "transaction_state_machine",
    "audit",
]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}

FIRST_IPC_NUMBERS = ("", "1", "ipc-1", "ipc 1", "ipc_1")


def _money(value: float) -> float:
    return formulas.round_money(value)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    item_code = _support.text_of(record, "boq_item").upper()
    line = contract_data.boq_item(item_code) if item_code else None
    if item_code and line is None:
        return refuse(
            f"boq_item {item_code!r} is not in the uploaded BOQ; known items: "
            + ", ".join(item["item"] for item in contract_data.boq_lines()),
            error_kind="unknown_boq_item",
        )

    gross = _support.number_of(record, "gross_amount", 0.0)
    if gross <= 0 and line:
        gross = float(line["amount"])
    # A nil certificate is a legitimate submission (no work valued in the
    # period). It is recorded as gross 0, not refused and not invented.

    accepted = _support.number_of(
        record, "accepted_contract_amount", contract_data.boq_total()
    ) or contract_data.boq_total()
    retention_pct = _support.number_of(record, "retention_pct", contract_data.RETENTION_PCT)
    if retention_pct <= 0:
        retention_pct = contract_data.RETENTION_PCT
    retention_pct = min(max(retention_pct, 0.0), 100.0)
    retention = formulas.retention_amount(gross, retention_pct)

    ipc_number = _support.text_of(record, "ipc_number")
    ps_rate = _support.number_of(
        record, "performance_security_rate", contract_data.PERFORMANCE_SECURITY_RATE_PCT
    )
    if ps_rate <= 0:
        ps_rate = contract_data.PERFORMANCE_SECURITY_RATE_PCT
    first_ipc = ipc_number.strip().lower() in FIRST_IPC_NUMBERS
    performance_security = formulas.performance_security(
        accepted, ps_rate, applies=bool(first_ipc and gross > 0)
    )
    net = formulas.net_after_deductions(gross, retention, performance_security)
    release = formulas.retention_release(retention)
    release_at_taking_over = release["at_taking_over"]
    release_at_dnp_end = release["at_dnp_end"]
    currency = _support.text_of(record, "currency") or "SAR"

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = f"boq_{uuid.uuid4().hex[:12]}"
    boq_csv = contract_data.write_boq_csv(workspace, stem)
    boq_xlsx = contract_data.write_boq_xlsx(workspace, stem)
    certificate = {
        "reference": reference,
        "ipc_number": ipc_number or reference,
        "boq_item": item_code,
        "period": _support.text_of(record, "period"),
        "gross_amount": gross,
        "retention_pct": retention_pct,
        "retention_amount": retention,
        "performance_security_rate_pct": ps_rate,
        "performance_security_deduction": performance_security,
        "net_certified": net,
        "currency": currency,
        "release_at_taking_over": release_at_taking_over,
        "release_at_dnp_end": release_at_dnp_end,
        "clauses": {"retention": "14.3", "performance_security": "4.2"},
    }
    certificate_file = workspace / f"ipc_{reference.replace('/', '_')}_{uuid.uuid4().hex[:8]}.json"
    certificate_file.write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")

    validation_item = {
        "id": item_code or reference,
        "type": "boq_line",
        "description": (line or {}).get("description", reference),
        "quantity": (line or {}).get("quantity", 1.0),
        "unit": (line or {}).get("unit", "sum"),
        "value": gross,
        "cost": gross,
    }
    inputs: Dict[str, Dict[str, Any]] = {
        "finance_reconciliation": {
            "left_records": [{"account_id": item_code or reference, "amount": gross}],
            "right_records": [{"account_id": item_code or reference, "amount": net}],
            "group_by": ["account_id"],
            "amount_field": "amount",
        },
        "finance_canonical_model": {
            "operation": "normalize_record",
            "record_type": "invoice",
            "record": {
                "amount": net,
                "currency": currency,
                "reference": reference,
                "description": f"Interim Payment Certificate {ipc_number or reference}",
            },
        },
        "boq_processor": {"file_path": str(boq_csv), "text": str(boq_xlsx)},
        "validation": {"item": validation_item, "context": {"capability": CAPABILITY_ID}},
        "approval_rules": {
            "project_id": "harbourline-civil-works",
            "source_doc": contract_data.CONTRACT_DOCUMENT,
            "extracted": [],
        },
        "transaction_state_machine": {
            "entity_id": f"ipc:{reference}",
            "vertical": "transaction",
            "event": "post_offers",
            "actor": "provider",
            "transition_id": f"submit:{reference}",
        },
        "audit": {
            "action_type": "ipc_certified",
            "principal_id": _support.text_of(record, "prepared_by") or "contract-administrator",
            "payload": certificate,
            "result": {"net_certified": net, "reference": reference},
            "reference": reference,
        },
    }

    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID, record, BLOCK_IDS, inputs, actions={"approval_rules": "ingest"}
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result = {
        **certificate,
        "accepted_contract_amount": accepted,
        "retained_to_date": retention,
        "net_payable": net,
        "block_evidence": {
            "reconciled": isinstance(answers.get("finance_reconciliation"), dict)
            and answers["finance_reconciliation"].get("ok") is not False,
            "canonicalised": isinstance(answers.get("finance_canonical_model"), dict)
            and answers["finance_canonical_model"].get("ok") is not False,
            "boq_parsed": isinstance(answers.get("boq_processor"), dict)
            and answers["boq_processor"].get("ok") is not False,
            "approval_ingested": isinstance(answers.get("approval_rules"), dict)
            and answers["approval_rules"].get("ok") is not False,
            "ledger_transition": isinstance(answers.get("transaction_state_machine"), dict)
            and answers["transaction_state_machine"].get("ok") is not False,
        },
        "certificate_file": str(certificate_file),
        "citation": contract_data.BOQ_DOCUMENT,
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 3 formulas",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
