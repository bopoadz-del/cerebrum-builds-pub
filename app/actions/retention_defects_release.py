"""retention_defects_release — retention releases and the performance security.

Clause 14.3 of document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf
holds 5% of each Interim Payment Certificate, released 50% at Taking-Over and
50% at the end of the Defects Notification Period; Clause 11.1 sets that
period at 365 days; Clause 4.2 sets the performance security at 10% of the
Accepted Contract Amount. Every rate and period is an operator setting.

READS:  the capability payload, the contract excerpt, block answers.
WRITES: the release schedule returned to the route (the route persists it).
NEVER:  releases retention without a named approver, or answers ok around a
        failed block.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

from app import contract, dispatch, formulas, models, security
from app.actions._common import (
    BlockRefused,
    as_date,
    as_float,
    call,
    currency_code,
    envelope,
    refusal,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "retention_defects_release"
ENTITY = "retention_defects_release"
BLOCK_IDS = ["finance_planning", "transaction_state_machine", "notification"]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_CONTRACT = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.RetentionDefectsRelease.from_dict(data)
    record = model.to_dict()

    gross = as_float(data.get("gross_certified_amount"), 0.0)
    taking_over = as_date(data.get("taking_over_date"))
    stage = str(data.get("release_stage") or "").strip()
    if stage and stage not in models.RetentionDefectsRelease.allowed_values("release_stage"):
        return refusal(
            "release_stage must be one of: "
            + ", ".join(models.RetentionDefectsRelease.allowed_values("release_stage")),
            field="release_stage",
        )

    retention_rate = float(contract.term("retention_rate"))
    retention_held = float(
        formulas.evaluate("retention_amount", certified_amount=gross, retention_rate=retention_rate)
    )
    first_share = float(contract.term("retention_release_first_share"))
    defects_end = None
    if taking_over is not None:
        defects_end = formulas.evaluate(
            "defects_notification_end",
            taking_over_date=taking_over.isoformat(),
            defects_notification_days=contract.term_int("defects_notification_days"),
        )

    share = {
        "taking_over": first_share,
        "defects_end": 1.0 - first_share,
        "final": 1.0,
    }.get(stage or "taking_over", first_share)
    already = 0.0 if stage in {"", "taking_over", "final"} else retention_held * first_share
    release = formulas.evaluate(
        "retention_release_share", retention_held=retention_held, share=share, already_released=already
    )

    decision = str(data.get("approval_decision") or "none")
    approver = None
    if decision == "release":
        approver = security.require_approver(str(data.get("approved_by") or ""), "retention release")
    elif decision == "hold":
        release = {"amount": "0.00", "remaining": f"{retention_held:.2f}", "share": "0"}

    aca = float(contract.boq_total())
    performance_security = float(
        formulas.evaluate("performance_security_amount", accepted_contract_amount=aca)
    )
    reference = str(data.get("reference") or data.get("certificate_reference") or "retention")

    budget_payload: Dict[str, Any] = {
        "action": "create_budget",
        "tenant_id": str(tenant_id),
        "amount": str(release["amount"]),
        "period": (taking_over or _dt.date.today()).strftime("%Y-%m"),
    }
    currency = currency_code()
    if currency:
        budget_payload["currency_code"] = currency

    try:
        budget = call("finance_planning", budget_payload, action=None)
        transition = call(
            "transaction_state_machine",
            {
                "entity_id": reference,
                "vertical": "order",
                "event": "accept",
                "actor": "provider",
            },
            action="transition",
        )
        notified = call(
            "notification",
            {
                "channel": "mcp",
                "block": "notification",
                "tool": "retention_release",
                "message": (
                    f"Retention release {reference}: {release['amount']} due at "
                    f"stage {stage or 'taking_over'}"
                ),
                "payload": {"reference": reference, "amount": str(release["amount"])},
            },
            action="send",
        )
    except BlockRefused as exc:
        return refusal(exc.message)

    result = {
        "release": {
            "certificate_reference": data.get("certificate_reference"),
            "gross_certified_amount": gross,
            "retention_rate": retention_rate,
            "retention_held": f"{retention_held:.2f}",
            "release_stage": stage or "taking_over",
            "share": str(share),
            "release_amount": release["amount"],
            "retention_remaining": release["remaining"],
            "taking_over_date": taking_over.isoformat() if taking_over else None,
            "defects_notification_end_date": defects_end,
            "performance_security_amount": f"{performance_security:.2f}",
            "contract_clauses": ["14.3", "11.1", "4.2"],
        },
        "approval": {
            "decision": decision,
            "approved_by": approver,
            "released": decision == "release",
        },
        "finance_planning": {
            "budget_id": (budget.get("budget") or {}).get("id"),
            "amount": (budget.get("budget") or {}).get("amount"),
            "status": (budget.get("budget") or {}).get("status"),
        },
        "state": {
            "from": transition.get("from_state"),
            "to": transition.get("to_state"),
            "terminal": transition.get("terminal"),
        },
        "notification": {
            "channel": notified.get("channel"),
            "sent": notified.get("sent"),
            "status": notified.get("status"),
        },
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": _CONTRACT,
        },
    }
    record["gross_certified_amount"] = gross
    record["performance_security_amount"] = performance_security
    record["taking_over_date"] = taking_over.isoformat() if taking_over else record.get("taking_over_date")
    record["defects_notification_end_date"] = defects_end or record.get("defects_notification_end_date")
    record["release_stage"] = stage or "taking_over"
    if decision == "release":
        record["status"] = "closed"
    elif decision == "hold":
        record["status"] = "in_progress"
    return envelope(record, result)
