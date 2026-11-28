"""Fail-closed booking lifecycle.

The vendored transaction_state_machine block is the source of the lifecycle
vocabulary.  This capability maps the booking states onto it, enforces which
transitions are legal and who may make them, and returns the customer and
contractor view at each state.  An illegal transition or an unpermitted actor
is refused as a decision, never accepted as a successful move.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute

CAPABILITY_ID = "booking_status_lifecycle"
ENTITY = "booking_status_lifecycle"
BLOCK_IDS = ["transaction_state_machine"]
BLOCK_DEFAULT_ACTIONS = {"transaction_state_machine": "transition"}
AUTHORED_BY = "codewhale exec"

STATES = ["requested", "accepted", "in_progress", "completed", "cancelled"]
NEXT_STATES = {
    "requested": ["accepted", "cancelled"],
    "accepted": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}
ALLOWED_ACTORS = {
    "requested": ["customer", "operator", "system"],
    "accepted": ["contractor", "operator"],
    "in_progress": ["contractor"],
    "completed": ["contractor", "operator"],
    "cancelled": ["customer", "contractor", "operator", "system"],
}
VIEWS = {
    "requested": {"customer": "booking requested", "contractor": "new booking request"},
    "accepted": {"customer": "booking confirmed", "contractor": "booking accepted"},
    "in_progress": {"customer": "contractor is working", "contractor": "job in progress"},
    "completed": {"customer": "booking completed", "contractor": "job completed"},
    "cancelled": {"customer": "booking cancelled", "contractor": "booking cancelled"},
}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    current = str(data.get("current_state") or "requested")
    target = str(data.get("target_state") or current)
    actor = str(data.get("actor") or "system")
    booking = str(data.get("booking_reference") or data.get("reference") or "booking")

    # The block's default is "transition"; the lifecycle definition ("machine")
    # is what this decision needs, so the handler reads the states from the
    # block and enforces the booking rules on top of them.
    machine = execute(
        "transaction_state_machine",
        {"vertical": "task"},
        action="machine",
    )
    if block_failed(machine):
        return fail(refusal_text(machine))
    block_states = machine.get("states") or {}

    if current not in STATES or target not in STATES:
        return fail("unknown booking state", error_kind="validation_error",
                    rejected_field="target_state", allowed_values=STATES)

    allowed = target in NEXT_STATES.get(current, [])
    reason = "legal transition" if allowed else "invalid_transition"
    if allowed and current != target and actor not in ALLOWED_ACTORS.get(target, []):
        allowed = False
        reason = "actor_not_permitted"

    return ok({
        "booking_reference": booking,
        "from_state": current,
        "to_state": target,
        "actor": actor,
        "allowed": allowed,
        "decision": reason,
        "allowed_next": NEXT_STATES.get(current, []),
        "views": VIEWS.get(target, {}),
        "block_states": sorted(block_states.keys()),
        "authority": {"label": "certified", "layer": 1, "basis": "transaction_state_machine/task"},
    })
