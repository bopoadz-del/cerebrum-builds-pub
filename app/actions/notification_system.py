"""notification_system — REUSE notification + event_bus + queue + workflow."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import event_bus_input, notice_workflow_input, notification_input, queue_input
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import allowed_next_status, envelope_status, notice_priority
from app.persist import ok_envelope

# READS: caller.input, env.process, config.runtime, queue.jobs
# WRITES: caller.output, notification.outbound, queue.jobs
# NEVER: (none)

BLOCK_IDS = ["notification", "event_bus", "queue", "workflow"]
CAPABILITY_ID = "notification_system"
KINDS = ("confirmation", "reminder", "update")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a guest notice on MCP with prepared event_bus workflow steps and persist it."""
    status = envelope_status(payload)
    notice_kind = str(payload.get("notice_kind") or "confirmation")
    if notice_kind not in KINDS:
        notice_kind = "confirmation"
    guest_name = str(payload.get("guest_name") or payload.get("reference") or "sample")
    priority = notice_priority(notice_kind)
    record = {
        **payload,
        "status": status,
        "notice_kind": notice_kind,
        "guest_name": guest_name,
        "priority": priority,
        "event": f"hotel.notice.{notice_kind}",
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "notification": notification_input(record),
        "event_bus": event_bus_input(record),
        "queue": queue_input(record),
        "workflow": notice_workflow_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["notice"] = {
        "guest_name": guest_name,
        "notice_kind": notice_kind,
        "priority": priority,
        "channel": "mcp",
        "allowed_next_status": list(allowed_next_status(status)),
        "pipeline": f"notice-{record.get('reference') or 'sample'}",
        "steps": ["step_0", "step_1", "step_2"],
        "queued": True,
        "notified": True,
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
