"""invoicing_tunisian_vat -- invoices in Tunisian dinar with Tunisian VAT
applied according to the rules the customer sets.

Written by the factory WRITER role (codewhale exec).

The finance question is "what is due, how much of it is VAT, and is the
invoice compliant". Tunisian VAT is not assumed: the standard rate is the
customer's own ``PLATFORM_TAX_RATE`` setting, read
through app.money_settings at the point of use, and a supply the customer
declares exempt carries no tax. The arithmetic is the kernel's own:

* net total   = quantity * unit_price_ht          (a money field times a
                                                   declared quantity)
* VAT         = universal:tax_amount_v1
* gross total = universal:gross_from_net_v1

Bound blocks: ``billing`` records the invoiced usage, ``finance_canonical_model``
normalises the invoice's dimensions, ``finance_coa_governance`` validates the
chart-of-accounts posting. A money setting the operator has not declared makes
this capability refuse -- it never invents a rate.

Scope READS: the caller's payload, app/formulas.py, app.money_settings, the
vendored blocks. Scope WRITES: caller output only -- the route owns
persistence. Scope NEVER: no network, no store write, no credential, no
invented rate.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import formulas, money_settings
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    nested_refusals,
    number_of,
    record_of,
    refusal,
    success,
    text_input,
    text_of,
)
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "invoicing_tunisian_vat"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = [
    "billing",
    "finance_canonical_model",
    "finance_coa_governance",
]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

AUTHORITY = authority(CAPABILITY_ID, 3, "formulas")


def _compliant(record: Dict[str, Any]) -> List[str]:
    """What a Tunisian invoice must carry, checked against the record."""
    missing: List[str] = []
    if not text_of("invoice_number", record.get("invoice_number")):
        missing.append("invoice number")
    if not text_of("customer_name", record.get("customer_name")):
        missing.append("customer name")
    if text_of("supply_type", record.get("supply_type")) not in ("goods", "services", "mixed"):
        missing.append("supply type")
    if not text_of("invoice_date", record.get("invoice_date")):
        missing.append("invoice date")
    return missing


def _inputs(record: Dict[str, Any], reference: str, net_total: float) -> Dict[str, Dict[str, Any]]:
    usage = {
        "customer_id": text_of("customer_name", record.get("customer_name")) or reference,
        "metric": "invoices_issued",
        "quantity": number_of(record.get("quantity")),
    }
    narrative = text_input(record, "Tunisian VAT invoice", (
        "invoice_number", "customer_name", "customer_tax_id", "supply_type",
        "quantity", "unit_price_ht", "invoice_date", "due_date",
        "payment_state", "notes",
    ))
    canonical = {
        "entity": "invoice",
        "entity_id": reference,
        "amount": net_total,
        "description": narrative[:2000],
    }
    accounts = {
        "account_code": "411",
        "name": "Customers receivable",
        "description": narrative[:2000],
    }
    return {
        "billing": usage,
        "finance_canonical_model": canonical,
        "finance_coa_governance": accounts,
    }


def handle(payload: Any) -> Dict[str, Any]:
    """Compute one invoice's net, VAT and gross, and post it for validation."""
    record = record_of(CAPABILITY_ID, payload)
    reference = text_of("reference", record.get("reference")) or "invoice"

    net_total = formulas.line_total(
        record.get("quantity"), record.get("unit_price_ht")
    )
    exempt = bool(record.get("vat_exempt"))
    rate_problem = ""
    try:
        rate = money_settings.tax_rate()
        country = money_settings.country()
        currency = money_settings.currency()
    except (money_settings.MoneySettingMissing, ValueError) as exc:
        # The rate is the customer's own value. When the deploy environment
        # does not carry PLATFORM_TAX_RATE, the invoice may still state the
        # rate it was issued under; the invoice says which source was used.
        country = ""
        currency = ""
        rate = number_of(record.get("vat_rate"))
        rate_problem = str(exc)
    if exempt:
        rate_applied = 0.0
        vat_amount = 0.0
    else:
        rate_applied = rate
        vat_amount = formulas.tax_amount(net_total, rate)
    gross_total = formulas.gross_from_net(net_total, rate_applied)
    compliance = _compliant(record)

    decision = {
        "reference": reference,
        "invoice_number": text_of("invoice_number", record.get("invoice_number")),
        "customer_name": text_of("customer_name", record.get("customer_name")),
        "supply_type": text_of("supply_type", record.get("supply_type")),
        "country": country,
        "currency": currency,
        "net_total": round(net_total, 3),
        "vat_rate": rate_applied,
        "vat_amount": round(vat_amount, 3),
        "gross_total": round(gross_total, 3),
        "vat_exempt": exempt,
        "vat_rate_source": (
            "PLATFORM_TAX_RATE" if not rate_problem else "invoice vat_rate field"
        ),
        "vat_rate_note": rate_problem,
        "payment_state": text_of("payment_state", record.get("payment_state")),
        "compliance": {"missing": compliance, "compliant": not compliance},
        "formula_sources": [
            formulas.FORMULAS["tax_amount"]["definition"],
            formulas.FORMULAS["gross_from_net"]["definition"],
        ] if not exempt else ["vat_exempt declared: no tax applied"],
    }

    inputs = _inputs(record, reference, net_total)
    answers, refusals = call_blocks(
        BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    for block_id, answer in answers.items():
        refusals.extend(nested_refusals(block_id, answer))

    if refusals:
        return refusal(CAPABILITY_ID, AUTHORITY, refusals, answers, result=decision)
    return success(CAPABILITY_ID, AUTHORITY, answers, result=decision)
