"""Supplier cost, parts pricing and invoicing in the declared currency."""

from __future__ import annotations

from typing import Any, Dict

from app import formulas, money_settings
from app.actions._common import block_failure, envelope
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "supplier_cost_and_parts_pricing"
ENTITY = "supplier_cost_and_parts_pricing"
BLOCK_IDS = [
    "finance_canonical_model",
    "finance_import",
    "finance_data_quality",
    "finance_reconciliation",
    "validation",
]
BLOCK_DEFAULT_ACTIONS = {
    "finance_canonical_model": None,
    "finance_import": None,
    "finance_data_quality": None,
    "finance_reconciliation": None,
    "validation": "validate_pipeline",
}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "config", "scope": "runtime"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    calls = [
        ("finance_canonical_model", execute("finance_canonical_model", {}, action=BLOCK_DEFAULT_ACTIONS.get("finance_canonical_model"))),
        ("finance_import", execute("finance_import", {"rows": [], "source_type": "gl"}, action=BLOCK_DEFAULT_ACTIONS.get("finance_import"))),
        ("finance_data_quality", execute("finance_data_quality", {"records": []}, action=BLOCK_DEFAULT_ACTIONS.get("finance_data_quality"))),
        ("finance_reconciliation", execute("finance_reconciliation", {"left_records": [], "right_records": []}, action=BLOCK_DEFAULT_ACTIONS.get("finance_reconciliation"))),
        (
            "validation",
            execute(
                "validation",
                {"target": {"id": CAPABILITY_ID, "type": "capability", "name": CAPABILITY_ID}},
                action=BLOCK_DEFAULT_ACTIONS.get("validation"),
            ),
        ),
    ]
    for block_id, answer in calls:
        refused = block_failure(block_id, answer)
        if refused:
            return refused

    unit_cost = _number(record.get("unit_cost_mad"))
    price = _number(record.get("price_mad"))
    quantity = int(_number(record.get("quantity")) or 1)
    amount = _number(record.get("amount_mad")) or round(price * quantity, 2)

    pricing: Dict[str, Any] = {
        "currency": money_settings.currency(),
        "country": money_settings.country(),
        "quantity": quantity,
        "amount": amount,
        "markup_ratio": None,
        "tax_amount": None,
    }
    if unit_cost > 0 and price > 0:
        pricing["markup_ratio"] = round(formulas.markup_on_cost(price, unit_cost), 6)
    if amount > 0:
        try:
            pricing["tax_amount"] = round(formulas.tax_amount(amount, money_settings.tax_rate()), 2)
        except money_settings.MoneySettingMissing:
            pricing["tax_amount"] = None
            pricing["tax_note"] = "PLATFORM_TAX_RATE is not set"

    return envelope(
        {
            "invoice_reference": str(record.get("invoice_reference") or ""),
            "supplier": str(record.get("supplier") or ""),
            "part_number": str(record.get("part_number") or ""),
            "pricing": pricing,
            "authority": {"layer": 3, "label": "formulas"},
            "workflow": {
                "import": len((calls[1][1] or {}).get("accepted") or []),
                "quality_gate": (calls[2][1] or {}).get("gate"),
                "reconciliation": (calls[3][1] or {}).get("reconciliation_status"),
                "validation_stages": len((calls[4][1] or {}).get("stages") or []),
            },
        },
        record,
    )
