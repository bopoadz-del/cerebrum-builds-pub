"""defects_notification_period: Clause 11.1.

Opens the 365-day Defects Notification Period at Taking-Over, logs defect
notifications with close-out evidence, and triggers release of the second
half of the Clause 14.3 retention when the period ends. The defects and
maintenance system is a declared placeholder connector.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from app import contract_data
from app.action_support import (
    BlockCallFailed,
    as_date,
    answer,
    call_block,
    clause_setting,
    refused,
    round_money,
)
from app.block_inputs import default_block_action

CAPABILITY_ID = "defects_notification_period"
ENTITY = "defects_notification_period"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["estate_maintenance", "workflow", "notification", "audit"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    taking_over = as_date(record.get("taking_over_date"))
    dnp_days = int(clause_setting("PLATFORM_RATE_DNP_DAYS", 365))
    dnp_end = taking_over + timedelta(days=dnp_days)
    defect_ref = str(record.get("defect_ref") or reference)
    evidence = str(record.get("closeout_evidence") or "")
    closed = bool(evidence.strip())
    release = round_money(float(record.get("retention_release_amount") or 0.0))
    if release <= 0:
        release = round_money(contract_data.boq_total() * 0.05 * 0.5)

    try:
        work_order = call_block(
            "estate_maintenance",
            {"title": f"defect {defect_ref}: {record.get('defect_description') or 'notification'}",
             "due": dnp_end.isoformat(),
             "status": "closed" if closed else "open"},
            action=BLOCK_DEFAULT_ACTIONS.get("estate_maintenance"),
        )
        routing = call_block(
            "workflow",
            {
                "pipeline_id": "defects_notification_closeout",
                "steps": [
                    {"id": "step_0", "block": "validation", "action": "validate_pipeline",
                     "input": {"pipeline": {"id": CAPABILITY_ID, "type": "pipeline"}}},
                ],
            },
            action=BLOCK_DEFAULT_ACTIONS.get("workflow"),
        )
        notice = call_block(
            "notification",
            {"message": f"defect {defect_ref} " + ("closed out" if closed else "open at DNP end"),
             "to": "commercial-team"},
            action=BLOCK_DEFAULT_ACTIONS.get("notification"),
            params={"channel": "mcp", "tool": "audit"},
        )
        logged = call_block(
            "audit",
            {"event": "defects_notification", "reference": reference,
             "defect_ref": defect_ref, "closed": closed},
            action=BLOCK_DEFAULT_ACTIONS.get("audit"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "taking_over_date": taking_over.isoformat(),
            "dnp_days": dnp_days,
            "dnp_end": dnp_end.isoformat(),
            "defect_ref": defect_ref,
            "closeout_evidence": evidence,
            "closed_out": closed,
            "retention_release_due": release,
            "release_trigger": "end_of_defects_notification_period",
            "work_order_id": (work_order or {}).get("id") if isinstance(work_order, dict) else None,
            "workflow_status": routing.get("status") if isinstance(routing, dict) else None,
            "notification_sent": bool(notice.get("sent")) if isinstance(notice, dict) else False,
            "audit_entry": ((logged or {}).get("entry") or {}).get("id") if isinstance(logged, dict) else None,
            "clauses": {"11.1": contract_data.CLAUSES["11.1"], "14.3": contract_data.CLAUSES["14.3"]},
        },
        authority="2:documents",
    )
