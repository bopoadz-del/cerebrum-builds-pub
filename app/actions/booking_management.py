"""booking_management — REUSE workflow + database + validation + event_bus + queue + audit."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import (
    audit_input,
    booking_workflow_input,
    database_input,
    event_bus_input,
    queue_input,
    validation_input,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import (
    allowed_next_status,
    booking_cascade,
    envelope_status,
    nightly_rate,
    stay_nights,
    stay_total,
)
from app.persist import ok_envelope

# READS: caller.input, env.process, config.runtime, database.sql, queue.jobs
# WRITES: caller.output, database.sql, queue.jobs
# NEVER: (none)

BLOCK_IDS = ["workflow", "database", "validation", "event_bus", "queue", "audit"]
CAPABILITY_ID = "booking_management"
STAY_KINDS = ("night", "week", "group")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reserve a stay with prepared event_bus workflow steps and persist the booking."""
    status = envelope_status(payload)
    stay_kind = str(payload.get("stay_kind") or "night")
    if stay_kind not in STAY_KINDS:
        stay_kind = "night"
    room_label = str(payload.get("room_label") or payload.get("reference") or "sample")
    nights = stay_nights(stay_kind)
    rate = nightly_rate(status)
    total = stay_total(status, stay_kind)
    cascade = booking_cascade(stay_kind)
    record = {
        **payload,
        "status": status,
        "stay_kind": stay_kind,
        "room_label": room_label,
        "stay_nights": nights,
        "nightly_rate": rate,
        "stay_total": total,
        "event": f"hotel.booking.{stay_kind}",
        "next_action": cascade["next_action"],
        "hold_minutes": cascade["hold_minutes"],
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "workflow": booking_workflow_input(record),
        "database": database_input(record),
        "validation": validation_input(record),
        "event_bus": event_bus_input(record),
        "queue": queue_input(record),
        "audit": audit_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["booking"] = {
        "stay_kind": stay_kind,
        "room_label": room_label,
        "stay_nights": nights,
        "nightly_rate": rate,
        "stay_total": total,
        "next_action": cascade["next_action"],
        "hold_minutes": cascade["hold_minutes"],
        "queue": cascade["queue"],
        "allowed_next_status": list(allowed_next_status(status)),
        "pipeline": f"booking-{record.get('reference') or 'sample'}",
        "steps": ["step_0", "step_1", "step_2"],
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
