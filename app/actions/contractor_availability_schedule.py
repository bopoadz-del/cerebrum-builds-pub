"""Contractor availability calendar.

No Store block supplies a schedule calendar, so the slot algebra is authored
here and declared as the writer formulas ``delivery:slot_count_v1`` and
``delivery:slot_open_capacity_v1`` (labelled "improvised, no Store coverage";
see ``app/formulas/writer_definitions.jsonl`` and
``docs/provenance/provenance.json``).  A recurring weekly window is validated,
split into bookable slots, and each slot is marked with the bookings that
already occupy it.  The customer booking filter and the matching step read the
same shape.

A window whose end is at or before its start runs past midnight -- an evening
shift is not an error.  When start and end are equal the contractor published
a whole-day window.

SCALE: one weekly window (or one whole-day window) per call.
READS: caller fields, the tenant's schedules and bookings for the slot count.
WRITES: the computed slot list in the response; the route persists the record.
NEVER: a slot marked free when a live booking already overlaps it.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain_rules, formulas
from app.action_common import fail, ok

CAPABILITY_ID = "contractor_availability_schedule"
ENTITY = "contractor_availability_schedule"
BLOCK_IDS = []
BLOCK_DEFAULT_ACTIONS = {}
AUTHORED_BY = "codewhale exec"


def _bookings_for(contractor: str, weekday: str) -> List[Dict[str, Any]]:
    wanted = domain_rules.normalise_area(contractor)
    out = []
    for row in domain_rules.tenant_records(domain_rules.BOOKING_ENTITY):
        if domain_rules.normalise_area(row.get("contractor_reference")) != wanted:
            continue
        if str(row.get("status") or "") == "closed":
            continue
        if domain_rules.weekday_of(row.get("booking_date")) != weekday:
            continue
        out.append(row)
    return out


def _slots(start: int, end: int, capacity: int, slot_minutes: int,
           bookings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    cursor = start
    index = 0
    while cursor + slot_minutes <= end:
        slot_end = cursor + slot_minutes
        booked = 0
        for booking in bookings:
            other_start = domain_rules.minutes(booking.get("start_time"))
            if other_start is None:
                continue
            other_start, other_end, _ = domain_rules.shift_window(
                other_start, domain_rules.minutes(booking.get("end_time")),
                domain_rules.service_minutes(),
            )
            if other_start < slot_end and other_end > cursor:
                booked += 1
        slots.append({
            "slot": index,
            "start": domain_rules.clock(cursor),
            "end": domain_rules.clock(slot_end),
            "start_minute": cursor,
            "end_minute": slot_end,
            "capacity": capacity,
            "booked": booked,
            "available": booked < capacity,
        })
        cursor = slot_end
        index += 1
    return slots


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "availability")
    contractor = str(data.get("contractor_reference") or "").strip()
    weekday = str(data.get("weekday") or "").strip().casefold()
    slot_minutes = domain_rules.slot_length()

    start = domain_rules.minutes(data.get("start_time"))
    end = domain_rules.minutes(data.get("end_time"))
    if start is None or end is None:
        return fail("start_time and end_time must be clock values",
                    error_kind="validation_error", rejected_field="start_time")
    if weekday not in domain_rules.VALID_WEEKDAYS:
        return fail("weekday must be a day of the week",
                    error_kind="validation_error", rejected_field="weekday")

    capacity = int(data.get("capacity") or 1)
    if capacity < 1:
        return fail("capacity must be at least 1", error_kind="validation_error",
                    rejected_field="capacity")
    active = domain_rules.truthy(data.get("active"), default=True)

    # Equal clock values mean a whole-day window; an end before the start is
    # an evening shift that crosses midnight.
    if end == start:
        window_start, window_end, crosses = 0, domain_rules.DAY_MINUTES, False
    else:
        window_start, window_end, crosses = domain_rules.shift_window(start, end, 0)
    if window_end <= window_start:
        window_end += domain_rules.DAY_MINUTES

    bookings = _bookings_for(contractor, weekday) if active else []
    slots = _slots(window_start, window_end, capacity, slot_minutes, bookings)
    if not active:
        slots = [{**slot, "available": False} for slot in slots]

    window_minutes = window_end - window_start
    slot_count = int(formulas.evaluate(
        "delivery:slot_count_v1",
        {"window_minutes": window_minutes, "slot_minutes": slot_minutes},
    ))
    booked_count = sum(slot["booked"] for slot in slots)
    open_capacity = int(formulas.evaluate(
        "delivery:slot_open_capacity_v1",
        {"slot_count": slot_count, "capacity": capacity, "booked_count": booked_count},
    ))
    if not active:
        open_capacity = 0
    open_slots = sum(1 for slot in slots if slot["available"])
    slot_authority = formulas.authority("delivery:slot_count_v1")
    capacity_authority = formulas.authority("delivery:slot_open_capacity_v1")
    return ok({
        "contractor_reference": contractor,
        "weekday": weekday,
        "window": {
            "start": domain_rules.clock(window_start),
            "end": domain_rules.clock_end(window_end),
            "crosses_midnight": crosses,
            "whole_day": start == end,
        },
        "duration_minutes": window_minutes,
        "slot_minutes": slot_minutes,
        "capacity_per_slot": capacity,
        "slot_count": slot_count,
        "slots_listed": len(slots),
        "booked_slots": sum(1 for slot in slots if slot["booked"]),
        "booked_count": booked_count,
        "open_slots": open_slots,
        "open_capacity": open_capacity,
        "schedule_reference": reference,
        "slots": slots,
        "authority": slot_authority,
        "formula_sources": [
            "delivery:slot_count_v1",
            "delivery:slot_open_capacity_v1",
        ],
        # Every figure carries the computation it came from.  The two slot
        # formulas are improvised (no kernel or Store coverage) and say so;
        # the direct counts are this capability's own procedure over the
        # caller's window and the tenant's own bookings.
        "claims": {
            "duration_minutes": {
                "value": window_minutes,
                "basis": "resolved working window (end - start, midnight-crossing added)",
                "authority": {"label": "procedure", "layer": 4},
            },
            "slot_minutes": {
                "value": slot_minutes,
                "basis": "PLATFORM_SLOT_MINUTES operator setting (app.domain_rules.slot_length)",
                "authority": {"label": "procedure", "layer": 4},
            },
            "slot_count": {
                "value": slot_count,
                "basis": "delivery:slot_count_v1 (window_minutes // slot_minutes)",
                "authority": slot_authority,
            },
            "open_capacity": {
                "value": open_capacity,
                "basis": "delivery:slot_open_capacity_v1 (slot_count * capacity - booked_count)",
                "authority": capacity_authority,
            },
            "open_slots": {
                "value": open_slots,
                "basis": "count of listed slots whose booked count is below capacity",
                "authority": {"label": "procedure", "layer": 4},
            },
            "booked_slots": {
                "value": sum(1 for slot in slots if slot["booked"]),
                "basis": "slots overlapped by a live tenant booking",
                "authority": {"label": "procedure", "layer": 4},
            },
        },
    })
