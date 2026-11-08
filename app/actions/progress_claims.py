"""progress_claims -- Interim Payment Certificates against BOQ items.

The commercial question is not "store a claim": it is what can be certified
this period, what retention the contract withholds, what (if anything) is
released this period, and what is therefore payable.

The handler answers that and has the BOQ, finance, formula, workflow,
approval and state-machine blocks check the figures and the route the
certificate takes. Persistence is the route's job -- a handler has no tenant.

Scope READS: caller payload, app/sources.py, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only.
Scope NEVER: no network, no contract figure invented, no rate the operator
did not set.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Dict, List

from app import formulas, sources
from app.actions._artifacts import Workspace
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    currency,
    money_round,
    number_of,
    record_of,
    refusal,
    success,
    text_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "progress_claims"
ENTITY = CAPABILITY_ID

BLOCK_IDS = [
    "boq_processor", "finance_canonical_model", "formula_executor",
    "workflow", "approval_rules", "pdf", "transaction_state_machine",
]

_BOQ_ACTION = "parse" if importlib.util.find_spec("pandas") is not None else "health"

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "boq_processor": _BOQ_ACTION,
    "finance_canonical_model": "schema",
    "formula_executor": "evaluate",
    "workflow": "run",
    "approval_rules": "ledger",
    "pdf": None,
    "transaction_state_machine": "transition",
}

AUTHORITY = authority(CAPABILITY_ID, 2, "documents")


def _boq_rows() -> List[List[Any]]:
    rows: List[List[Any]] = [
        ["item", "description", "unit", "qty", "rate (%s)" % currency()]
    ]
    for item in sources.boq_rows():
        rows.append(
            [item["item"], item["description"], item["unit"], item["qty"], item["rate"]]
        )
    return rows


def _released_share(taking_over: bool, defects_notified: bool) -> float:
    clause = sources.clause(sources.clause_number("retention")) or {}
    at_taking_over = float(clause.get("release_taking_over_percent", 50.0))
    at_dnp_end = float(clause.get("release_dnp_end_percent", 50.0))
    share = 0.0
    if taking_over:
        share += at_taking_over
    if defects_notified:
        share += at_dnp_end
    return share


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    item = sources.boq_item(record.get("boq_item"))
    quantity = number_of(record.get("measured_quantity"))
    rate = number_of(record.get("unit_rate"))
    if item is not None:
        if quantity <= 0:
            quantity = number_of(item.get("qty"))
        if rate <= 0:
            rate = number_of(item.get("rate"))
    if quantity <= 0 and rate <= 0 and item is not None:
        quantity = number_of(item.get("qty"))
        rate = number_of(item.get("rate"))
    line_value = formulas.boq_line_value(quantity, rate)
    gross = number_of(record.get("certified_amount"))
    if gross <= 0:
        gross = line_value

    taking_over = bool(record.get("taking_over"))
    defects_notified = bool(record.get("defects_notified"))
    if defects_notified and not taking_over:
        return refusal(
            CAPABILITY_ID,
            AUTHORITY,
            [
                "retention: the second half is released at the end of the "
                "Defects Notification Period (Clause %s, from Taking-Over); "
                "Taking-Over has not occurred"
                % sources.clause_number("defects_notification")
            ],
            {},
            input_digest=record.get("_input_digest"),
        )

    declared_retention = record.get("retention_percent")
    retention_percent = (
        number_of(declared_retention)
        if number_of(declared_retention) > 0
        else sources.clause_value("retention")
    )
    retention = formulas.retention_amount(gross, retention_percent)
    released = formulas.retention_release(
        retention, _released_share(taking_over, defects_notified)
    )
    net = formulas.net_payable(gross, retention, released)

    reference = text_of(record.get("reference")) or "draft"
    ipc_number = text_of(record.get("ipc_number")) or text_of(record.get("reference")) or "IPC-draft"
    period = text_of(record.get("period")) or "current"
    boq_item = text_of(record.get("boq_item")) or (item["item"] if item else "measured")

    workspace = Workspace("harbourline-ipc-")
    try:
        try:
            boq_file = workspace.xlsx("harbourline_boq.xlsx", _boq_rows())
        except Exception:
            boq_file = workspace.csv("harbourline_boq.csv", _boq_rows())
        boq_input: Dict[str, Any] = {}
        if _BOQ_ACTION == "parse":
            boq_input = {"file_path": boq_file, "currency": currency()}
        inputs: Dict[str, Dict[str, Any]] = {
            "boq_processor": boq_input,
            "finance_canonical_model": {"operation": "schema"},
            "formula_executor": {
                "formula_description": "IPC retention under Clause %s"
                % sources.clause_number("retention"),
                "custom_code": "result = certified_amount * retention_percent / 100",
                "input_values": {
                    "certified_amount": gross,
                    "retention_percent": retention_percent,
                },
            },
            "workflow": {
                "pipeline_id": "ipc-certificate-%s" % reference,
                "trigger": "progress_claim_certified",
                "steps": [
                    {
                        "block": "event_bus",
                        "action": "publish",
                        "input": {
                            "topic": "progress_claim.certified",
                            "payload": {
                                "reference": reference,
                                "ipc_number": ipc_number,
                                "gross_certified": money_round(gross),
                                "currency": currency(),
                            },
                            "message": "Interim Payment Certificate %s certified"
                            % ipc_number,
                            "channel": "mcp",
                            "tool": "event_bus",
                        },
                    }
                ],
            },
            "approval_rules": {
                "action": "ledger",
                "project_id": reference,
                "source_doc": sources.CONTRACT_DOCUMENT,
            },
            "pdf": {"file_path": boq_file},
            "transaction_state_machine": {
                "operation": "transition",
                "entity_id": "ipc-%s" % reference,
                "vertical": "transaction",
                "event": "post_offers",
                "actor": "provider",
                "transition_id": record.get("_input_digest"),
            },
        }
        answers, refusals = call_blocks(
            BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
        )
    finally:
        workspace.close()

    if refusals:
        return refusal(
            CAPABILITY_ID, AUTHORITY, refusals, answers,
            input_digest=record.get("_input_digest"),
        )

    formula = answers.get("formula_executor") or {}
    block_retention = number_of(
        formula.get("execution_result")
        if isinstance(formula, dict) and "execution_result" in formula
        else (formula.get("result") or {}).get("execution_result")
        if isinstance(formula.get("result"), dict)
        else None,
        -1.0,
    )
    if block_retention >= 0 and abs(block_retention - retention) > 0.01:
        return refusal(
            CAPABILITY_ID,
            AUTHORITY,
            [
                "formula_executor: retention %.2f disagrees with the Clause %s "
                "result %.2f"
                % (block_retention, sources.clause_number("retention"), retention)
            ],
            answers,
            input_digest=record.get("_input_digest"),
        )

    return success(
        CAPABILITY_ID,
        AUTHORITY,
        answers,
        input_digest=record.get("_input_digest"),
        result={
            "ipc_number": ipc_number,
            "period": period,
            "boq_item": boq_item,
            "boq_line_value": line_value,
            "currency": currency(),
            "gross_certified": money_round(gross),
            "retention_percent": retention_percent,
            "retention_amount": retention,
            "retention_released": released,
            "net_payable": net,
            "taking_over": taking_over,
            "defects_notified": defects_notified,
            "clauses": {
                "retention": sources.clause_number("retention"),
                "defects_notification": sources.clause_number("defects_notification"),
            },
            "decision": "certify" if gross > 0 else "no measurable value certified",
            "citation": sources.CONTRACT_DOCUMENT,
        },
    )
