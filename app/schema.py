"""Capability specs. Envelope vocabulary is schema-enforced: open | in_progress | closed."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

STATUS_VALUES = ("open", "in_progress", "closed")
RESERVED_FIELDS = frozenset({"action", "id"})

ENVELOPE_FIELDS: Dict[str, Dict[str, Any]] = {
    "reference": {"type": "string"},
    "status": {"type": "string"},
}

ENVELOPE_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "status": {"allowed_values": list(STATUS_VALUES)},
}


def _spec(
    capability_id: str,
    block_ids: List[str],
    extra_fields: Mapping[str, Dict[str, Any]] | None = None,
    extra_constraints: Mapping[str, Dict[str, Any]] | None = None,
    entity: str | None = None,
) -> Dict[str, Any]:
    fields = {**ENVELOPE_FIELDS, **(extra_fields or {})}
    constraints = {**ENVELOPE_CONSTRAINTS, **(extra_constraints or {})}
    return {
        "id": capability_id,
        "entity": entity or capability_id,
        "FIELDS": fields,
        "CONSTRAINTS": constraints,
        "BLOCK_IDS": list(block_ids),
    }


SPECS: Dict[str, Dict[str, Any]] = {
    "booking_management": _spec(
        "booking_management",
        ["workflow", "database", "validation", "event_bus", "queue", "audit"],
        extra_fields={
            "stay_kind": {"type": "string"},
            "room_label": {"type": "string"},
        },
        extra_constraints={
            "stay_kind": {"allowed_values": ["night", "week", "group"]},
        },
    ),
    "property_management": _spec(
        "property_management",
        ["database", "team", "workflow", "audit"],
        extra_fields={
            "property_kind": {"type": "string"},
            "property_name": {"type": "string"},
        },
        extra_constraints={
            "property_kind": {"allowed_values": ["hotel", "resort", "boutique"]},
        },
    ),
    "dynamic_pricing": _spec(
        "dynamic_pricing",
        ["formula_executor", "recommendation_template", "analytics", "database"],
        extra_fields={
            "season": {"type": "string"},
            "rate_plan": {"type": "string"},
        },
        extra_constraints={
            "season": {"allowed_values": ["peak", "shoulder", "off"]},
        },
    ),
    "review_management": _spec(
        "review_management",
        ["capture", "knowledge", "vector_search", "analytics", "notification"],
        extra_fields={
            "rating_band": {"type": "string"},
            "guest_name": {"type": "string"},
        },
        extra_constraints={
            "rating_band": {"allowed_values": ["excellent", "good", "poor"]},
        },
    ),
    "analytics_dashboard": _spec(
        "analytics_dashboard",
        ["dashboard", "analytics", "database"],
        extra_fields={
            "view_name": {"type": "string"},
            "horizon": {"type": "string"},
        },
        extra_constraints={
            "horizon": {"allowed_values": ["today", "week", "month"]},
        },
    ),
    "notification_system": _spec(
        "notification_system",
        ["notification", "event_bus", "queue", "workflow"],
        extra_fields={
            "notice_kind": {"type": "string"},
            "guest_name": {"type": "string"},
        },
        extra_constraints={
            "notice_kind": {"allowed_values": ["confirmation", "reminder", "update"]},
        },
    ),
    "search_recommendation": _spec(
        "search_recommendation",
        ["vector_search", "knowledge", "recommendation_template", "memory", "analytics"],
        extra_fields={
            "stay_intent": {"type": "string"},
            "destination": {"type": "string"},
        },
        extra_constraints={
            "stay_intent": {"allowed_values": ["leisure", "business", "family"]},
        },
    ),
}

CAPABILITIES = SPECS
REQUIRED_CAPABILITY_IDS = tuple(SPECS.keys())


def get_spec(capability_id: str) -> Dict[str, Any]:
    try:
        return SPECS[capability_id]
    except KeyError as exc:
        raise KeyError(f"unknown capability: {capability_id}") from exc
