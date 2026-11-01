"""collection_planning_tracking -- plan, schedule and track coffee-waste
collections from cafes and other sources through to delivery.

Written by the factory WRITER role (codewhale exec).

The logistics question is not "was a row stored" but "is this pickup due, how
much will we lose against the plan, and what does the crew do next". The
handler answers with the collection's own arithmetic (shortfall against the
plan, expected compost yield from what arrived) and calls the three blocks the
blueprint bound to this capability:

* ``task_listing`` publishes the pickup as a work item the crew can claim;
* ``geolocation_tracking`` records the truck's position at the source;
* ``workflow`` runs the pickup pipeline tying the two together.

Scope READS: the caller's payload, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only -- the route owns persistence.
Scope NEVER: no network, no store write, no credential, no invented reading.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import formulas
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    nested_refusals,
    number_of,
    record_of,
    refusal,
    setting,
    setting_number,
    success,
    text_input,
    text_of,
)
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "collection_planning_tracking"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = ["task_listing", "geolocation_tracking", "workflow"]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

AUTHORITY = authority(CAPABILITY_ID, 3, "formulas")

DEFAULT_ADDRESS = "Tunis"
_TASK_CATEGORY = "delivery"


def _shortfall(record: Dict[str, Any]) -> Dict[str, Any]:
    planned = number_of(record.get("planned_kg"))
    collected = number_of(record.get("collected_kg"))
    pct = formulas.shortfall_pct(planned, collected)
    limit = setting_number("PICKUP_SHORTFALL_ALERT_PCT", 15.0)
    return {
        "planned_kg": planned,
        "collected_kg": collected,
        "shortfall_pct": pct,
        "alert": bool(planned > 0 and pct > limit),
        "alert_at_pct": limit,
    }


def _pickup_due(record: Dict[str, Any]) -> Dict[str, Any]:
    status = text_of("status", record.get("status")) or "open"
    delivered = bool(text_of("delivered_on", record.get("delivered_on")))
    return {
        "due": status in ("open", "in_progress") and not delivered,
        "delivered": delivered,
        "priority": text_of("priority", record.get("priority")) or "normal",
    }


def _inputs(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    reference = text_of("reference", record.get("reference")) or "collection"
    source = text_of("source_name", record.get("source_name")) or "coffee source"
    address = text_of("source_address", record.get("source_address")) or DEFAULT_ADDRESS
    lat = number_of(record.get("pickup_lat"))
    lng = number_of(record.get("pickup_lng"))
    title = "Collect coffee waste from %s (%s)" % (source, reference)
    listing = {
        "title": title[:140],
        "description": text_input(record, "Coffee-waste collection", (
            "reference", "source_name", "source_type", "pickup_date",
            "planned_kg", "collected_kg", "priority", "notes",
        ))[:5000],
        "category": _TASK_CATEGORY,
        "location": {"address": address, "lat": lat, "lng": lng},
    }
    position = {
        "entity_id": reference,
        "lat": lat,
        "lng": lng,
        "label": source,
    }
    steps = [
        {
            "id": "step_0",
            "block": "geolocation_tracking",
            "input": dict(position),
            "params": {"action": BLOCK_DEFAULT_ACTIONS.get("geolocation_tracking")},
        }
    ]
    return {
        "task_listing": listing,
        "geolocation_tracking": position,
        "workflow": {
            "pipeline_id": CAPABILITY_ID,
            "steps": steps,
            "result": {
                "reference": reference,
                "source_name": source,
                "planned_kg": number_of(record.get("planned_kg")),
                "collected_kg": number_of(record.get("collected_kg")),
            },
        },
    }


def handle(payload: Any) -> Dict[str, Any]:
    """Plan one coffee-waste collection and say what the crew does next."""
    record = record_of(CAPABILITY_ID, payload)
    reference = text_of("reference", record.get("reference"))
    source = text_of("source_name", record.get("source_name"))

    shortfall = _shortfall(record)
    due = _pickup_due(record)
    planned = shortfall["planned_kg"]
    collected = shortfall["collected_kg"]
    yield_ratio_note = ""
    try:
        expected_compost = formulas.compost_yield_kg(collected)
    except Exception as exc:  # a yield rate the operator has not set yet
        expected_compost = 0.0
        yield_ratio_note = "compost yield rate not configured (%s)" % type(exc).__name__

    actions_due: List[str] = []
    if due["due"]:
        actions_due.append("schedule_pickup")
    if collected > 0:
        actions_due.append("record_intake")
    if shortfall["alert"]:
        actions_due.append("chase_source")
    if due["delivered"]:
        actions_due.append("close_collection")

    decision = {
        "reference": reference,
        "source_name": source,
        "source_type": text_of("source_type", record.get("source_type")),
        "status": text_of("status", record.get("status")) or "open",
        "pickup": due,
        "shortfall": shortfall,
        "expected_compost_kg": expected_compost,
        "yield_note": yield_ratio_note,
        "moisture_pct": number_of(record.get("moisture_pct")),
        "actions_due": actions_due,
    }

    inputs = _inputs(record)
    answers, refusals = call_blocks(
        BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    for block_id, answer in answers.items():
        refusals.extend(nested_refusals(block_id, answer))

    if refusals:
        return refusal(CAPABILITY_ID, AUTHORITY, refusals, answers, result=decision)
    return success(CAPABILITY_ID, AUTHORITY, answers, result=decision)
