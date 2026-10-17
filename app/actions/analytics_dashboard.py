"""analytics_dashboard — REUSE dashboard + analytics + database."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import analytics_input, dashboard_input, database_input
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import (
    adr_for,
    allowed_next_status,
    dashboard_band,
    envelope_status,
    occupancy_pct,
    revpar,
)
from app.persist import ok_envelope

# READS: caller.input, config.runtime, database.sql
# WRITES: caller.output, database.sql
# NEVER: (none)

BLOCK_IDS = ["dashboard", "analytics", "database"]
CAPABILITY_ID = "analytics_dashboard"
HORIZONS = ("today", "week", "month")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Render occupancy / ADR / RevPAR and persist the hotel board."""
    status = envelope_status(payload)
    horizon = str(payload.get("horizon") or "today")
    if horizon not in HORIZONS:
        horizon = "today"
    view_name = str(payload.get("view_name") or payload.get("reference") or "sample")
    occupancy = occupancy_pct(status)
    adr = adr_for(horizon)
    revenue_per_room = revpar(status, horizon)
    record = {
        **payload,
        "status": status,
        "view_name": view_name,
        "horizon": horizon,
        "occupancy_pct": occupancy,
        "adr": adr,
        "revpar": revenue_per_room,
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "dashboard": dashboard_input(record),
        "analytics": analytics_input(record),
        "database": database_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["board"] = {
        "view_name": view_name,
        "horizon": horizon,
        "band": dashboard_band(horizon),
        "occupancy_pct": occupancy,
        "adr": adr,
        "revpar": revenue_per_room,
        "widgets": ["bookings", "occupancy", "revenue"],
        "allowed_next_status": list(allowed_next_status(status)),
        "theme": "light",
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
