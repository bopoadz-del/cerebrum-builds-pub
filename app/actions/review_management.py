"""review_management — REUSE capture + knowledge + vector_search + analytics + notification."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import (
    analytics_input,
    capture_input,
    knowledge_input,
    notification_input,
    vector_search_input,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import allowed_next_status, envelope_status, review_publish_state, review_score
from app.persist import ok_envelope

# READS: caller.input, config.runtime, database.vector, file.local.read
# WRITES: caller.output, database.vector, notification.outbound
# NEVER: (none)

BLOCK_IDS = ["capture", "knowledge", "vector_search", "analytics", "notification"]
CAPABILITY_ID = "review_management"
BANDS = ("excellent", "good", "poor")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Score a guest review, extract its text, and persist the publish state."""
    status = envelope_status(payload)
    rating_band = str(payload.get("rating_band") or "excellent")
    if rating_band not in BANDS:
        rating_band = "excellent"
    guest_name = str(payload.get("guest_name") or payload.get("reference") or "sample")
    score = review_score(rating_band)
    publish_state = review_publish_state(status)
    record = {
        **payload,
        "status": status,
        "rating_band": rating_band,
        "guest_name": guest_name,
        "review_score": score,
        "publish_state": publish_state,
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "capture": capture_input(record),
        "knowledge": knowledge_input(record),
        "vector_search": vector_search_input(record),
        "analytics": analytics_input(record),
        "notification": notification_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["review"] = {
        "guest_name": guest_name,
        "rating_band": rating_band,
        "review_score": score,
        "publish_state": publish_state,
        "allowed_next_status": list(allowed_next_status(status)),
        "recorded": True,
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
