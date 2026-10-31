"""Threshold alerts on supplier cost and parts price movements."""

from __future__ import annotations

from typing import Any, Dict

from app.actions._common import block_failure, configured_email, envelope
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "cost_price_movement_alerts"
ENTITY = "cost_price_movement_alerts"
BLOCK_IDS = ["approval_rules", "notification", "email", "analytics", "dashboard"]
BLOCK_DEFAULT_ACTIONS = {
    "approval_rules": None,
    "notification": "send",
    "email": "validate_address",
    "analytics": "track_event",
    "dashboard": "render",
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
    missing = [
        name for name in ("threshold_mad", "previous_price_mad", "current_price_mad")
        if record.get(name) in (None, "")
    ]
    if missing:
        # A movement needs both prices and the manager's threshold. Coercing
        # an absent price to zero invents a critical breach.
        return {"ok": False, "error": "missing_price_input", "missing": missing,
                "capability_id": CAPABILITY_ID}
    reference = str(record.get("alert_reference") or record.get("reference") or "price-movement")
    threshold = _number(record.get("threshold_mad"))
    previous = _number(record.get("previous_price_mad"))
    current = _number(record.get("current_price_mad"))
    delta = round(current - previous, 2)
    breached = bool(threshold > 0 and abs(delta) >= threshold)
    level = str(record.get("alert_level") or ("critical" if breached and abs(delta) >= 2 * threshold else "warning"))

    rules = execute("approval_rules", {"action": "list"}, action=BLOCK_DEFAULT_ACTIONS.get("approval_rules"))
    refused = block_failure("approval_rules", rules)
    if refused:
        return refused

    notice = execute(
        "notification",
        {
            "channel": "mcp",
            "block": "audit",
            "payload": {"reference": reference, "delta_mad": delta},
            "message": f"Alert {reference}: price movement {delta}",
        },
        action=BLOCK_DEFAULT_ACTIONS.get("notification"),
    )
    refused = block_failure("notification", notice)
    if refused:
        return refused

    mail = execute(
        "email",
        {"email": configured_email(record)},
        action=BLOCK_DEFAULT_ACTIONS.get("email"),
    )
    refused = block_failure("email", mail)
    if refused:
        return refused

    metric = execute(
        "analytics",
        {"metric": "cost_price_movement", "value": abs(delta)},
        action=BLOCK_DEFAULT_ACTIONS.get("analytics"),
    )
    refused = block_failure("analytics", metric)
    if refused:
        return refused

    board = execute(
        "dashboard",
        {"user_id": str(record.get("plant") or "manager")},
        action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
    )
    refused = block_failure("dashboard", board)
    if refused:
        return refused

    return envelope(
        {
            "alert_reference": reference,
            "part_number": str(record.get("part_number") or ""),
            "threshold_mad": threshold,
            "delta_mad": delta,
            "breached": breached,
            "alert_level": level,
            "notification_sent": bool(notice.get("sent")),
            "email_valid": bool(mail.get("valid")),
            "email_sent": False,
            "email_delivery": "outlook adapter not configured; address validated only",
            "analytics_tracked": bool(metric.get("tracked")),
            "approval_sets": len((rules.get("result") or {}).get("sets") or rules.get("sets") or []),
            "dashboard_widgets": len(board.get("widgets") or []),
        },
        record,
    )
