"""search_recommendation — REUSE vector_search + knowledge + recommendation_template + memory + analytics."""

from __future__ import annotations

from typing import Any, Dict

from app.block_inputs import (
    analytics_input,
    knowledge_input,
    memory_input,
    recommendation_template_input,
    vector_search_input,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.domain import allowed_next_status, envelope_status, match_score
from app.persist import ok_envelope

# READS: caller.input, config.runtime, database.vector, memory.cache
# WRITES: caller.output, database.vector, memory.cache
# NEVER: (none)

BLOCK_IDS = ["vector_search", "knowledge", "recommendation_template", "memory", "analytics"]
CAPABILITY_ID = "search_recommendation"
INTENTS = ("leisure", "business", "family")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Match a stay intent and persist a ranked hotel recommendation."""
    status = envelope_status(payload)
    stay_intent = str(payload.get("stay_intent") or "leisure")
    if stay_intent not in INTENTS:
        stay_intent = "leisure"
    destination = str(payload.get("destination") or payload.get("reference") or "sample")
    score = match_score(stay_intent)
    rank = 1 if score >= 0.8 else 2
    record = {
        **payload,
        "status": status,
        "stay_intent": stay_intent,
        "destination": destination,
        "match_score": score,
        "recommend_rank": rank,
        "capability": CAPABILITY_ID,
        "channel": "mcp",
    }
    prepared = {
        "vector_search": vector_search_input(record),
        "knowledge": knowledge_input(record),
        "recommendation_template": recommendation_template_input(record),
        "memory": memory_input(record),
        "analytics": analytics_input(record),
    }
    blocks: Dict[str, Any] = {}
    for block_id in BLOCK_IDS:
        blocks[block_id] = execute(
            block_id,
            prepared[block_id],
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    record["recommendation"] = {
        "stay_intent": stay_intent,
        "destination": destination,
        "match_score": score,
        "recommend_rank": rank,
        "allowed_next_status": list(allowed_next_status(status)),
        "searched": True,
    }
    return ok_envelope(CAPABILITY_ID, record, blocks)
