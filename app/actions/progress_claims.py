"""progress_claims: interim payment certificates under Clause 14.3.

Prepares and certifies an IPC against the BOQ line items, applies the 5%
retention of Clause 14.3, and states the 50/50 release points. The
accounting ledger is a declared placeholder connector, so the route
answers its typed 503 before this handler runs; handle() still performs
the certificate arithmetic for composition and the smoke contract.
"""

from __future__ import annotations

from typing import Any, Dict

from app import contract_data, formulas
from app.action_support import (
    AUTHORITY_DOCUMENTS,
    BlockCallFailed,
    as_date,
    as_float,
    answer,
    call_block,
    clause_setting,
    currency,
    refused,
    round_money,
)
from app.block_inputs import default_block_action

CAPABILITY_ID = "progress_claims"
ENTITY = "progress_claims"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = [
    "finance_reconciliation",
    "finance_reconciliation_workflow",
    "validation",
    "document_engine",
    "workflow",
]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    item = contract_data.boq_item(str(record.get("boq_item") or ""))
    gross = as_float(record.get("gross_amount"), 0.0)
    if gross <= 0 and item:
        gross = round_money(item["qty"] * item["rate"])
    retention_pct = formulas.retention_pct()
    retention = formulas.retention_amount(gross, retention_pct)
    net = formulas.net_after_retention(gross, retention_pct)
    split = formulas.release_split(retention)
    release_at_taking_over = split["at_taking_over"]
    release_at_dnp_end = split["at_dnp_end"]
    period = str(record.get("period") or as_date(record.get("issued_date")).isoformat()[:7])

    try:
        reconciliation = call_block(
            "finance_reconciliation",
            {
                "left_records": [{"account_id": str(record.get("boq_item") or item.get("item") or "IPC"),
                                  "amount": gross}],
                "right_records": [{"account_id": str(record.get("boq_item") or item.get("item") or "IPC"),
                                   "amount": net}],
                "group_by": ["account_id"],
                "amount_field": "amount",
            },
            action=BLOCK_DEFAULT_ACTIONS.get("finance_reconciliation"),
        )
        run = call_block(
            "finance_reconciliation_workflow",
            {
                "tenant_id": tenant_id,
                "project_id": "harbourline-civil-works",
                "run_type": "actuals_vs_budget",
                "source_period": period,
                "created_by": str(record.get("preparer_id") or "contract-administrator"),
            },
            action=BLOCK_DEFAULT_ACTIONS.get("finance_reconciliation_workflow"),
        )
        check = call_block(
            "validation",
            {
                "pipeline": {"id": CAPABILITY_ID, "type": "pipeline"},
                "blocks": [CAPABILITY_ID],
                "required_tests": ["unit"],
            },
            action=BLOCK_DEFAULT_ACTIONS.get("validation"),
        )
        parsed = call_block(
            "document_engine",
            {"text": " ".join(contract_data.CLAUSES.values())},
            action=BLOCK_DEFAULT_ACTIONS.get("document_engine"),
        )
        pipeline = call_block(
            "workflow",
            {
                "pipeline_id": "progress_claim_certification",
                "steps": [
                    {
                        "id": "step_0",
                        "block": "validation",
                        "action": "validate_pipeline",
                        "input": {"pipeline": {"id": CAPABILITY_ID, "type": "pipeline"}},
                    }
                ],
            },
            action=BLOCK_DEFAULT_ACTIONS.get("workflow"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "ipc": str(record.get("ipc_number") or reference),
            "boq_item": item,
            "gross_amount": gross,
            "retention_pct": retention_pct,
            "retention_amount": retention,
            "net_certified": net,
            "release_at_taking_over": release_at_taking_over,
            "release_at_dnp_end": release_at_dnp_end,
            "currency": str(record.get("currency") or currency()),
            "boq_total": contract_data.boq_total(),
            "clauses": {"14.3": contract_data.CLAUSES["14.3"]},
            "reconciliation_status": reconciliation.get("reconciliation_status"),
            "reconciliation_run": run.get("run", {}).get("id"),
            "validation_status": (check.get("status") if isinstance(check, dict) else None),
            "document_sections": sorted((parsed.get("requirements") or {}).keys())[:5]
            if isinstance(parsed, dict) else [],
            "workflow_status": pipeline.get("status"),
        },
        authority=AUTHORITY_DOCUMENTS,
    )
