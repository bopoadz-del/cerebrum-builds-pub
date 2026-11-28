"""Domain rules shared by the delivery capabilities.

These are the decisions the brief asks for -- slot algebra, the service-area
check, the double-booking overlap, and canonical digests -- kept in one place
so the booking filter, the schedule and the matching step read the same rule.
Nothing here is a named case: every function is driven by the caller's own
fields and the records already stored for the caller's tenant.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app import store, tenancy

DAY_MINUTES = 24 * 60
VALID_WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)
BOOKING_ENTITY = "customer_booking_flow"
CONTRACTOR_ENTITY = "contractor_onboarding_and_service_areas"
SCHEDULE_ENTITY = "contractor_availability_schedule"
SERVICE_SUBURB_ENTITY = "service_suburb"
TERMINAL_BOOKING_STATUSES = {"closed", "cancelled", "canceled"}


def minutes(value: Any) -> Optional[int]:
    """A clock value as minutes after midnight, or None when malformed."""
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def clock(value: int) -> str:
    minute = int(value) % DAY_MINUTES
    return "%02d:%02d:00" % (minute // 60, minute % 60)


def clock_end(value: int) -> str:
    """Like clock(), but a window ending at midnight reads 24:00, not 00:00."""
    if int(value) % DAY_MINUTES == 0 and int(value) > 0:
        return "24:00:00"
    return clock(value)


def slot_length() -> int:
    """Minutes in one bookable slot; an operator setting, not a code constant."""
    raw = (os.getenv("PLATFORM_SLOT_MINUTES") or "").strip()
    try:
        value = int(raw) if raw else 60
    except ValueError:
        value = 60
    if value < 5 or value > DAY_MINUTES:
        value = 60
    return value


def service_minutes() -> int:
    """Default service window when a booking gives no distinct end time."""
    raw = (os.getenv("PLATFORM_SERVICE_MINUTES") or "").strip()
    try:
        value = int(raw) if raw else 60
    except ValueError:
        value = 60
    if value < 5 or value > DAY_MINUTES:
        value = 60
    return value


def weekday_of(date_text: Any) -> Optional[str]:
    text = str(date_text or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%A").lower()
    except ValueError:
        return None


def shift_window(start: int, end: Optional[int], default_minutes: int) -> Tuple[int, int, bool]:
    """The real working window.

    An end at or before the start is a shift that runs past midnight (a night
    shift); when the two are equal the caller gave no distinct end, so the
    operator-configured service window applies.  A booking is therefore never
    zero-length, only a point in time that gets the standard window.
    """
    if end is None:
        return start, start + default_minutes, False
    if end == start:
        return start, start + default_minutes, False
    if end < start:
        return start, end + DAY_MINUTES, True
    return start, end, False


def normalise_area(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def split_areas(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").split(",")
    seen = set()
    out: List[str] = []
    for item in raw:
        cleaned = " ".join(item.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def tenant_records(entity: str) -> List[Dict[str, Any]]:
    """Records the current request's tenant owns; empty outside a request."""
    tenant_id = tenancy.current_tenant()
    if not tenant_id:
        return []
    try:
        return store.list_all(entity, tenant_id)
    except Exception:
        return []


def booking_holds_slot(row: Dict[str, Any]) -> bool:
    """Whether a stored booking still occupies its slot.

    A booking is live from the moment it is requested: requested, accepted
    and in progress all hold the contractor's slot; only a completed or
    cancelled booking (stored as ``closed``) releases it.  The one rule is
    shared by the booking handler, the route guard and the matching read.
    """
    status = str(row.get("status") or "").strip().casefold()
    return status not in TERMINAL_BOOKING_STATUSES


def overlapping_bookings(contractor: str, booking_date: str, start: int, end: int,
                         exclude_reference: str = "") -> List[Dict[str, Any]]:
    """Every live booking for the same contractor whose real window overlaps."""
    wanted = normalise_area(contractor)
    out: List[Dict[str, Any]] = []
    for row in tenant_records(BOOKING_ENTITY):
        if normalise_area(row.get("contractor_reference")) != wanted:
            continue
        if str(row.get("booking_date") or "") != str(booking_date or ""):
            continue
        if not booking_holds_slot(row):
            continue
        if exclude_reference and str(row.get("reference") or "") == exclude_reference:
            continue
        other_start = minutes(row.get("start_time"))
        other_end = minutes(row.get("end_time"))
        if other_start is None:
            continue
        other_start, other_end, _ = shift_window(other_start, other_end, service_minutes())
        if start < other_end and end > other_start:
            out.append(row)
    return out


def overlapping_booking(contractor: str, booking_date: str, start: int, end: int,
                        exclude_reference: str = "") -> Optional[Dict[str, Any]]:
    """Another live booking for the same contractor whose real window overlaps."""
    rows = overlapping_bookings(contractor, booking_date, start, end, exclude_reference)
    return rows[0] if rows else None


def suburb_catalogue() -> List[Dict[str, Any]]:
    """The tenant's managed suburb catalogue, as the ops back office keeps it."""
    return list(tenant_records(SERVICE_SUBURB_ENTITY))


def catalogue_areas(active_only: bool = True) -> Dict[str, Dict[str, Any]]:
    """Normalised suburb name -> catalogue row."""
    out: Dict[str, Dict[str, Any]] = {}
    for row in suburb_catalogue():
        if active_only and not truthy(row.get("active"), default=True):
            continue
        name = normalise_area(row.get("suburb"))
        if name:
            out[name] = row
    return out


def partition_areas(areas: Iterable[str], catalogue: Dict[str, Dict[str, Any]]
                    ) -> Tuple[List[str], List[str]]:
    """Split a contractor's selection into catalogue-approved and pending."""
    approved: List[str] = []
    pending: List[str] = []
    for area in areas:
        if normalise_area(area) in catalogue:
            approved.append(area)
        else:
            pending.append(area)
    return approved, pending


def partition_selection(areas: Iterable[str]) -> Tuple[List[str], List[str], List[str]]:
    """What the contractor's own selection means against the ops catalogue.

    The contractor owns the selection: a suburb they pick is an active
    service area unless the ops catalogue explicitly retires it.  A suburb
    the catalogue has never seen is still a working service area, and is
    also proposed to ops so the catalogue can catch up.  Only a suburb the
    ops back office marked inactive is withheld.

    Returns ``(active, retired, proposed)``.
    """
    catalogue = catalogue_areas(active_only=False)
    active: List[str] = []
    retired: List[str] = []
    proposed: List[str] = []
    for area in areas:
        row = catalogue.get(normalise_area(area))
        if row is None:
            active.append(area)
            proposed.append(area)
        elif truthy(row.get("active"), default=True):
            active.append(area)
        else:
            retired.append(area)
    return active, retired, proposed


def contractor_service_areas(row: Optional[Dict[str, Any]]) -> List[str]:
    """The active suburbs a stored contractor record advertises."""
    if not row:
        return []
    return split_areas(row.get("service_suburbs"))


def contractor_profile(reference: str) -> Optional[Dict[str, Any]]:
    wanted = normalise_area(reference)
    for row in tenant_records(CONTRACTOR_ENTITY):
        if normalise_area(row.get("reference")) == wanted:
            return row
    return None


def contractor_schedule(reference: str, weekday: str) -> List[Dict[str, Any]]:
    wanted = normalise_area(reference)
    wanted_day = str(weekday or "").casefold()
    out = []
    for row in tenant_records(SCHEDULE_ENTITY):
        if normalise_area(row.get("contractor_reference")) != wanted:
            continue
        if wanted_day and str(row.get("weekday") or "").casefold() != wanted_day:
            continue
        if row.get("active") in (0, False):
            continue
        out.append(row)
    return out


def schedule_covers(reference: str, weekday: str, start: int, end: int) -> Optional[bool]:
    """True/False when the tenant has a schedule to judge by, None when none."""
    windows = contractor_schedule(reference, weekday)
    if not windows:
        return None
    for row in windows:
        open_start = minutes(row.get("start_time"))
        if open_start is None:
            continue
        open_start, open_end, _ = shift_window(open_start, minutes(row.get("end_time")),
                                              DAY_MINUTES)
        if start >= open_start and end <= open_end:
            return True
    return False


def slots_between(bookings: Iterable[Dict[str, Any]], booking_date: str,
                  start: int, end: int, length: int) -> List[Dict[str, Any]]:
    """Bookable slots in a real window, each marked with what occupies it.

    ``bookings`` are stored booking rows for the same contractor; a live
    booking holds the slots it overlaps.  The walk is pure arithmetic on the
    caller's window and the tenant's own bookings -- no named case.
    """
    out: List[Dict[str, Any]] = []
    if length < 1:
        length = 1
    cursor = int(start)
    index = 0
    while cursor + length <= int(end):
        slot_end = cursor + length
        booked = 0
        for row in bookings:
            if not booking_holds_slot(row):
                continue
            if booking_date and str(row.get("booking_date") or "") != str(booking_date):
                continue
            other_start = minutes(row.get("start_time"))
            if other_start is None:
                continue
            other_start, other_end, _ = shift_window(
                other_start, minutes(row.get("end_time")), service_minutes()
            )
            if other_start < slot_end and other_end > cursor:
                booked += 1
        out.append({
            "slot": index,
            "start": clock(cursor),
            "end": clock(slot_end),
            "start_minute": cursor,
            "end_minute": slot_end,
            "booked": booked,
        })
        cursor = slot_end
        index += 1
    return out


def contractor_open_slots(reference: str, weekday: str, booking_date: str,
                          start: Optional[int] = None,
                          end: Optional[int] = None) -> List[Dict[str, Any]]:
    """The contractor's published windows as individual bookable slots.

    Reads only the tenant's schedules and bookings for the named contractor
    and weekday.  A slot is open when fewer live bookings occupy it than the
    schedule's capacity allows.
    """
    length = slot_length()
    bookings = [row for row in tenant_records(BOOKING_ENTITY)
                if normalise_area(row.get("contractor_reference")) == normalise_area(reference)
                and (not booking_date or str(row.get("booking_date") or "") == str(booking_date))]
    out: List[Dict[str, Any]] = []
    for window in contractor_schedule(reference, weekday):
        open_start = minutes(window.get("start_time"))
        open_end = minutes(window.get("end_time"))
        if open_start is None:
            continue
        open_start, open_end, crosses = shift_window(open_start, open_end, DAY_MINUTES)
        capacity = int(window.get("capacity") or 1)
        for slot in slots_between(bookings, booking_date, open_start, open_end, length):
            if start is not None and end is not None:
                if slot["start_minute"] < start or slot["end_minute"] > end:
                    continue
            slot.update({
                "capacity": capacity,
                "available": slot["booked"] < capacity,
                "crosses_midnight": crosses,
                "weekday": weekday,
            })
            out.append(slot)
    return out


def serving_contractors(suburb: str) -> List[Dict[str, Any]]:
    """Active contractors whose own service areas include ``suburb``."""
    wanted = normalise_area(suburb)
    out: List[Dict[str, Any]] = []
    for row in tenant_records(CONTRACTOR_ENTITY):
        if not truthy(row.get("active"), default=True):
            continue
        areas = contractor_service_areas(row)
        if wanted and wanted not in {normalise_area(area) for area in areas}:
            continue
        out.append(row)
    return out


def canonical_digest(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def as_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def iter_areas(rows: Iterable[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in rows:
        out.extend(split_areas(row.get("service_suburbs")))
    return out
