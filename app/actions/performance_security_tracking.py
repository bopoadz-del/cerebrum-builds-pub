"""performance_security_tracking: Clause 4.2 performance security.

Tracks a 10% performance security against the Accepted Contract Amount,
records issue and expiry, and raises an alert ahead of expiry or on a
change in the Accepted Contract Amount. The bank guarantee provider is a
declared placeholder connector, so the route answers its typed 503.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from app import contract_data, formulas
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

CAPABILITY_ID = "performance_security_tracking"
ENTITY = "performance_security_tracking"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["workflow", "notification", "dashboard"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    aca = contract_data.accepted_contract_amount(float(record.get("accepted_contract_amount") or 0))
    pct = clause_setting("PLATFORM_RATE_PERFORMANCE_SECURITY_PCT", 10.0)
    required_security = formulas.performance_security(aca, pct)
    recorded_security = round_money(float(record.get("security_amount") or required_security))
    expiry = as_date(record.get("expiry_date"))
    alert_days = int(clause_setting("PLATFORM_RATE_SECURITY_ALERT_DAYS", 30))
    today = as_date(record.get("today"))
    days_to_expiry = (expiry - today).days
    shortfall = round_money(required_security - recorded_security)
    alerts = []
    if days_to_expiry <= alert_days:
        alerts.append("expiry_within_" + str(alert_days) + "_days")
    if shortfall > 0:
        alerts.append("security_below_clause_4_2")

    try:
        routing = call_block(
            "workflow",
            {
                "pipeline_id": "performance_security_review",
                "steps": [
                    {"id": "step_0", "block": "validation", "action": "validate_pipeline",
                     "input": {"pipeline": {"id": CAPABILITY_ID, "type": "pipeline"}}},
                ],
            },
            action=BLOCK_DEFAULT_ACTIONS.get("workflow"),
        )
        notice = call_block(
            "notification",
            {"message": f"performance security {reference}: " + (",".join(alerts) or "current"),
             "to": str(record.get("issuer") or "commercial-team")},
            action=BLOCK_DEFAULT_ACTIONS.get("notification"),
            params={"channel": "mcp", "tool": "audit"},
        )
        board = call_block(
            "dashboard",
            {"widgets": [{"id": "performance_security", "type": "metric",
                          "value": recorded_security}]},
            action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    return answer(
        CAPABILITY_ID,
        {
            "instrument_number": str(record.get("instrument_number") or reference),
            "accepted_contract_amount": aca,
            "security_pct": pct,
            "required_security": required_security,
            "recorded_security": recorded_security,
            "shortfall": shortfall,
            "expiry_date": expiry.isoformat(),
            "days_to_expiry": days_to_expiry,
            "alert_threshold_days": alert_days,
            "alerts": alerts,
            "renewal_due": (expiry - timedelta(days=alert_days)).isoformat(),
            "notification_sent": bool(notice.get("sent")) if isinstance(notice, dict) else False,
            "workflow_status": routing.get("status") if isinstance(routing, dict) else None,
            "dashboard_widgets": len((board.get("widgets") or []) if isinstance(board, dict) else []),
            "clauses": {"4.2": contract_data.CLAUSES["4.2"]},
        },
        authority="2:documents",
    )
