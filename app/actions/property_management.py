"""property_management — REUSE database + team + workflow + audit."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import audit_input, database_input, property_workflow_input, team_input
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import allowed_next_status, envelope_status, property_band, property_room_count
from app.persist import ok_envelope

# READS: caller.input, env.process, config.runtime, database.sql, team.state
# WRITES: caller.output, database.sql, file.local.write
# NEVER: (none)

BLOCK_IDS = ["database", "team", "workflow", "audit"]
CAPABILITY_ID = "property_management"
KINDS = ("hotel", "resort", "boutique")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """List a property with a front-desk team and persist inventory."""
    status = envelope_status(payload)
    property_kind = str(payload.get("property_kind") or "hotel")
    if property_kind not in KINDS:
        property_kind = "hotel"
    property_name = str(payload.get("property_name") or payload.get("reference") or "sample")
    rooms = property_room_count(property_kind)
    band = property_band(property_kind)
    record = {
        **payload,
        "status": status,
        "property_kind": property_kind,
        "property_name": property_name,
        "room_count": rooms,
        "property_band": band,
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "database": database_input(record),
        "team": team_input(record),
        "workflow": property_workflow_input(record),
        "audit": audit_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["property"] = {
        "property_kind": property_kind,
        "property_name": property_name,
        "room_count": rooms,
        "property_band": band,
        "allowed_next_status": list(allowed_next_status(status)),
        "listed": True,
        "team_named": f"Hotel {property_name}",
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
