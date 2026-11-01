"""operational_dashboard -- collection status, batch progress, orders and
invoices, in one operational reading for internal staff.

Written by the factory WRITER role (codewhale exec).

The operator's question is "where does the factory stand today, and what needs
attention". The route measures the open queues from the tenant's own rows
(the model declares them in ``AGGREGATES``), so the handler receives a real
reading rather than typed counters, and answers with that reading's own
decisions (where the open work sits, what needs attention). It calls the two
bound blocks: ``dashboard`` renders the operator board, ``analytics`` records
that the board was rendered so usage is observable.

Scope READS: the caller's payload, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only -- the route owns persistence.
Scope NEVER: no network, no store write, no credential, no invented metric.
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
    text_of,
    whole_of,
)
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "operational_dashboard"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = ["dashboard", "analytics"]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

AUTHORITY = authority(CAPABILITY_ID, 3, "formulas")

_WIDGETS = [
    {"id": "collections", "type": "metric", "title": "Collections open"},
    {"id": "curing", "type": "metric", "title": "Batches in curing"},
    {"id": "orders", "type": "metric", "title": "Orders open"},
    {"id": "invoices", "type": "metric", "title": "Invoices unpaid"},
]


def _inputs(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    reference = text_of("reference", record.get("reference")) or "operations"
    board = {
        "title": "Factory operations %s" % (text_of("report_date", record.get("report_date")) or reference),
        "theme": setting("PLATFORM_DASHBOARD_THEME", "light"),
        "refresh_interval": int(formulas.setting_number("DASHBOARD_REFRESH_SECONDS", 30)),
        "widgets": [dict(widget) for widget in _WIDGETS],
    }
    return {
        "dashboard": board,
        "analytics": {"metric": "operational_dashboard_rendered", "value": 1},
    }


def handle(payload: Any) -> Dict[str, Any]:
    """Summarise the factory's operations and flag what needs attention."""
    record = record_of(CAPABILITY_ID, payload)
    collections_open = whole_of(record.get("collections_open"))
    curing = whole_of(record.get("batches_in_curing"))
    orders_open = whole_of(record.get("orders_open"))
    invoices_unpaid = whole_of(record.get("invoices_unpaid"))
    quality_failures = whole_of(record.get("quality_failures"))
    revenue = number_of(record.get("revenue_total"))

    total_work = collections_open + curing + orders_open + invoices_unpaid

    #: The open queues, in the order an operator reads them. The reading has
    #: no closed-work denominator (nothing on the record declares one), so a
    #: "completion share" would be a number invented from a hardcoded zero --
    #: what is reported instead is where the open work actually sits.
    queues = {
        "collections": collections_open,
        "curing": curing,
        "orders": orders_open,
        "invoices": invoices_unpaid,
    }
    busiest = max(queues, key=lambda name: (queues[name], name)) if total_work else ""

    attention: List[str] = []
    if collections_open > 0:
        attention.append("collections awaiting pickup")
    if invoices_unpaid > 0:
        attention.append("invoices unpaid")
    if quality_failures > 0:
        attention.append("batches that failed quality")
    threshold = formulas.setting_number("DASHBOARD_UNPAID_ALERT", 1.0)
    if invoices_unpaid >= threshold and threshold > 0:
        attention.append("unpaid invoices at or above the alert threshold")

    decision = {
        "reference": text_of("reference", record.get("reference")),
        "report_date": text_of("report_date", record.get("report_date")),
        "collections_open": collections_open,
        "batches_in_curing": curing,
        "orders_open": orders_open,
        "invoices_unpaid": invoices_unpaid,
        "quality_failures": quality_failures,
        "revenue_total": round(revenue, 3),
        "work_in_progress": total_work,
        "open_queues": queues,
        "busiest_queue": busiest,
        "busiest_queue_open": queues.get(busiest, 0) if busiest else 0,
        "attention_count": len(attention),
        "attention": attention,
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
