"""catalog_pricing_orders -- the product catalog, price lists, customers and
customer orders, including order lines and totals.

Written by the factory WRITER role (codewhale exec).

The sales desk's question is "what does this line cost the customer, and is
the price list and discount it was quoted from the one that applies". The
handler answers with the order's own arithmetic (discount from the kernel's
discount amount, net line total, price-list check) and calls the two bound
blocks: ``vendor_catalog`` registers the product in the catalog register,
``workflow`` runs the order pipeline.

Scope READS: the caller's payload, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only -- the route owns persistence.
Scope NEVER: no network, no store write, no credential, no invented price.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import formulas
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    nested_refusals,
    number_of,
    record_of,
    refusal,
    setting,
    success,
    text_input,
    text_of,
)
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "catalog_pricing_orders"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = ["vendor_catalog", "workflow"]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

AUTHORITY = authority(CAPABILITY_ID, 3, "formulas")

#: The catalog block declares a closed vendor category set.
_CATALOG_CATEGORY = "other"


def _pricing(record: Dict[str, Any]) -> Dict[str, Any]:
    quantity = number_of(record.get("quantity"))
    unit_price = number_of(record.get("unit_price"))
    gross_line = formulas.line_total(quantity, unit_price)
    discount_rate = number_of(record.get("discount_pct")) / 100.0
    discount = formulas.discount_amount(gross_line, discount_rate)
    net = formulas.net_price_after_discount(gross_line, discount_rate)
    return {
        "quantity": quantity,
        "unit_price": unit_price,
        "gross_line": gross_line,
        "discount_pct": number_of(record.get("discount_pct")),
        "discount_amount": discount,
        "net_total": net,
        "price_list": text_of("price_list", record.get("price_list")) or "retail",
    }


def _inputs(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    sku = text_of("product_sku", record.get("product_sku")) or "SKU"
    name = text_of("product_name", record.get("product_name")) or text_of(
        "customer_name", record.get("customer_name")
    ) or sku
    catalog = {
        "vendor_id": sku,
        "name": name,
        "categories": [_CATALOG_CATEGORY],
        "description": text_input(record, "Catalog entry", (
            "product_sku", "product_name", "price_list", "unit_price",
            "customer_type", "notes",
        ))[:2000],
    }
    steps = [
        {
            "id": "step_0",
            "block": "vendor_catalog",
            "input": dict(catalog),
            "params": {"action": BLOCK_DEFAULT_ACTIONS.get("vendor_catalog")},
        }
    ]
    return {
        "vendor_catalog": catalog,
        "workflow": {
            "pipeline_id": CAPABILITY_ID,
            "steps": steps,
            "result": {
                "reference": text_of("reference", record.get("reference")),
                "order_number": text_of("order_number", record.get("order_number")),
                "product_sku": sku,
            },
        },
    }


def handle(payload: Any) -> Dict[str, Any]:
    """Price one order line and register the product it sells."""
    record = record_of(CAPABILITY_ID, payload)
    pricing = _pricing(record)
    unit_price = pricing["unit_price"]
    low = number_of(setting("CATALOG_MIN_UNIT_PRICE", "0"))
    warnings: List[str] = []
    if unit_price < low:
        warnings.append("unit price is below the catalog floor %.3f" % low)
    if pricing["discount_pct"] > number_of(setting("CATALOG_MAX_DISCOUNT_PCT", "25")):
        warnings.append("discount exceeds the price-list authority")

    decision = {
        "reference": text_of("reference", record.get("reference")),
        "order_number": text_of("order_number", record.get("order_number")),
        "customer_name": text_of("customer_name", record.get("customer_name")),
        "customer_type": text_of("customer_type", record.get("customer_type")),
        "product_sku": text_of("product_sku", record.get("product_sku")),
        "product_name": text_of("product_name", record.get("product_name")),
        "order_date": text_of("order_date", record.get("order_date")),
        "pricing": pricing,
        "warnings": warnings,
    }

    inputs = _inputs(record)
    answers, refusals = call_blocks(
        BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    for block_id, answer in answers.items():
        refusals.extend(nested_refusals(block_id, answer))

    if refusals:
        return refusal(CAPABILITY_ID, AUTHORITY, refusals, answers, result=decision)
    return success(CAPABILITY_ID, AUTHORITY, answers, result=decision)
