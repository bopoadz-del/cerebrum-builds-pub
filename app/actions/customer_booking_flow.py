"""Customer browsing and booking with fail-closed slot validation.

The capability does two jobs the brief names together:

  * browse -- list the contractors whose own service areas include the
    requested suburb, whose published schedule covers the requested window,
    and whose open slots include it, together with those open slots;
  * book -- create a booking request after the same validation, refusing a
    slot already occupied by another live booking for the same contractor.

A booking names a contractor, a suburb and a date/slot.  The real working
window is resolved first (a shift may cross midnight; equal clock values get
the operator's standard service window, never a zero-length booking).  A
contractor that is on file must be active, must serve the suburb and, when a
schedule is on file, must cover the slot; a contractor that is not on file
cannot be advanced past a requested booking -- the answer says so and asks
ops to onboard before the lifecycle can accept it.

SCALE: one booking request per call.
READS: caller fields, the tenant's contractors, schedules and bookings.
WRITES: the browse/booking result in the response; the route persists it.
NEVER: a booking over another live booking at capacity, or into a suburb the
       contractor does not serve.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import domain_rules, formulas
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute

CAPABILITY_ID = "customer_booking_flow"
ENTITY = "customer_booking_flow"
BLOCK_IDS = ["task_listing"]
BLOCK_DEFAULT_ACTIONS = {"task_listing": "create"}
AUTHORED_BY = "codewhale exec"

# A booking is a request only while it is open; every later state means the
# customer/ops have confirmed an assignment and the contractor must verify.
REQUEST_STATES = {"open", "requested"}


def _profile(contractor: str, suburb: str) -> Dict[str, Any]:
    profile = domain_rules.contractor_profile(contractor) if contractor else None
    if profile is None:
        return {
            "contractor_registered": False,
            "contractor_active": None,
            "service_area_match": False,
            "contractor_capacity": None,
        }
    areas = domain_rules.contractor_service_areas(profile)
    wanted = domain_rules.normalise_area(suburb)
    return {
        "contractor_registered": True,
        "contractor_active": domain_rules.truthy(profile.get("active"), default=True),
        "service_area_match": wanted in {domain_rules.normalise_area(a) for a in areas},
        "contractor_capacity": int(profile.get("capacity") or 1),
    }


def _browse(suburb: str, booking_date: str, weekday: Optional[str],
            start: int, end: int) -> List[Dict[str, Any]]:
    """Contractors serving the suburb with a free, published slot in the window."""
    items: List[Dict[str, Any]] = []
    for row in domain_rules.serving_contractors(suburb):
        reference = str(row.get("reference") or "")
        if not reference:
            continue
        covered = domain_rules.schedule_covers(reference, weekday, start, end) if weekday else None
        if covered is False:
            continue
        slots = domain_rules.contractor_open_slots(reference, weekday, booking_date) if weekday else []
        open_in_window = [slot for slot in slots
                          if slot.get("available") and slot["start_minute"] >= start
                          and slot["end_minute"] <= end]
        if not open_in_window:
            continue
        items.append({
            "contractor_reference": reference,
            "contractor_name": row.get("contractor_name"),
            "service_areas": domain_rules.contractor_service_areas(row),
            "capacity": int(row.get("capacity") or 1),
            "schedule_checked": covered is not None,
            "open_slots": open_in_window,
        })
    items.sort(key=lambda item: (-len(item["open_slots"]), item["contractor_reference"]))
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    return items


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "booking")
    suburb = str(data.get("suburb") or "").strip()
    contractor = str(data.get("contractor_reference") or "").strip()
    booking_date = str(data.get("booking_date") or "").strip()
    status = str(data.get("status") or "open").strip() or "open"

    start = domain_rules.minutes(data.get("start_time"))
    end = domain_rules.minutes(data.get("end_time"))
    if start is None:
        return fail("start_time must be a clock value", error_kind="validation_error",
                    rejected_field="start_time")
    service = domain_rules.service_minutes()
    start, end, crosses = domain_rules.shift_window(start, end, service)
    if end - start < 1:
        return fail("end_time must be after start_time", error_kind="validation_error",
                    rejected_field="end_time")

    weekday = domain_rules.weekday_of(booking_date)
    profile = _profile(contractor, suburb)

    # Fail closed on the contractor that is on file: inactive, out of area,
    # or outside the published schedule is a refusal, never a silent pass.
    if profile["contractor_registered"]:
        if not profile["contractor_active"]:
            return fail("contractor is not active", error_kind="validation_error",
                        rejected_field="contractor_reference")
        if not profile["service_area_match"]:
            return fail(
                "contractor does not serve the booking suburb",
                error_kind="validation_error",
                rejected_field="suburb",
            )
        covered = domain_rules.schedule_covers(contractor, weekday, start, end) if weekday else None
        if covered is False:
            return fail(
                "contractor is not available for that slot",
                error_kind="validation_error",
                rejected_field="start_time",
            )
    else:
        covered = False
        # An unknown contractor may only sit on an open request; a booking
        # that claims a later lifecycle state needs a verified contractor.
        if status.casefold() not in REQUEST_STATES:
            return fail(
                "contractor is not onboarded; only an open booking request may name them",
                error_kind="validation_error",
                rejected_field="contractor_reference",
            )

    capacity = int(profile["contractor_capacity"] or 1) if profile["contractor_registered"] else 1
    overlapping = domain_rules.overlapping_bookings(contractor, booking_date, start, end)
    if len(overlapping) >= capacity:
        conflict = overlapping[0]
        return fail(
            "contractor already has a live booking in that slot",
            error_kind="conflict",
            conflicting_id=conflict.get("id"),
        )

    # Browse is the customer-facing half of the flow: who serves this suburb
    # and has this window free.  It is computed from the tenant's own records.
    browse = _browse(suburb, booking_date, weekday, start, end)
    named_open = (
        domain_rules.contractor_open_slots(contractor, weekday, booking_date)
        if contractor and weekday else []
    )

    quoted = domain_rules.as_number(data.get("quoted_amount"))
    cost = domain_rules.as_number(data.get("cost_amount"))
    profit = None
    if quoted is not None and cost is not None:
        profit = formulas.evaluate(
            "universal:gross_profit_v1", {"revenue": quoted, "cogs": cost}
        )

    listing = execute(
        "task_listing",
        {
            "title": "Delivery booking %s" % reference,
            "description": "Customer booking in %s on %s" % (suburb or "an unassigned suburb", booking_date),
            "category": "delivery",
            "location": {"address": suburb or "unassigned", "suburb": suburb},
            "budget": (
                {"min": quoted, "max": quoted} if quoted is not None else None
            ),
        },
        action=BLOCK_DEFAULT_ACTIONS.get("task_listing"),
    )
    if block_failed(listing):
        return fail(refusal_text(listing))

    verification = "verified" if profile["contractor_registered"] else "unregistered"
    return ok({
        "reference": reference,
        "status": status,
        "notes": str(data.get("notes") or ""),
        "customer_name": str(data.get("customer_name") or ""),
        "customer_email": str(data.get("customer_email") or ""),
        "service_type": str(data.get("service_type") or ""),
        "listing_id": listing.get("listing_id"),
        "contractor_reference": contractor,
        "booking_date": booking_date,
        "weekday": weekday,
        "slot": {
            "start": domain_rules.clock(start),
            "end": domain_rules.clock(end),
            "duration_minutes": end - start,
            "crosses_midnight": crosses,
        },
        **profile,
        "verification_state": verification,
        "assignment_state": (
            "confirmed_candidate" if profile["contractor_registered"]
            else "awaiting_contractor_onboarding"
        ),
        "ops_action_required": not profile["contractor_registered"],
        "schedule_checked": covered is not None,
        "slot_available": True,
        "slot_state": "free",
        "conflicting_id": None,
        "search": {
            "suburb": suburb,
            "booking_date": booking_date,
            "weekday": weekday,
            "window": {"start": domain_rules.clock(start), "end": domain_rules.clock(end)},
            "contractors": browse,
            "total": len(browse),
        },
        "open_slots": named_open,
        "gross_profit": profit,
        "quoted_amount": quoted,
        "authority": (
            {"label": "certified", "layer": 1, "basis": "universal:gross_profit_v1"}
            if profit is not None else
            {"label": "procedure", "layer": 4,
             "basis": "booking availability rules over tenant contractors, schedules and bookings"}
        ),
    })
