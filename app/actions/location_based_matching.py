"""Location-based matching of a booking to an available, active-suburb contractor.

Candidates come from the tenant's contractor records, not from the caller: a
contractor is a candidate only when the booking's suburb is one of the
contractor's own active service areas.  The published schedule then decides
availability -- a contractor whose schedule does not cover the requested
window (or who has published no schedule at all) is not a candidate for that
slot; it is reported in ``excluded`` with the reason, never ranked as if it
were free.  The vendored dispatch_matching block ranks the remaining
candidates and its own score decomposition is reported unchanged.

SCALE: one booking against the tenant's contractor set per call.
READS: caller fields, the tenant's contractors and schedules.
WRITES: the ranking in the response; the route persists the record.
NEVER: a candidate whose service areas exclude the suburb, or one that is
       not available for the requested slot.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute, execute_sequence

CAPABILITY_ID = "location_based_matching"
ENTITY = "location_based_matching"
BLOCK_IDS = ["dispatch_matching"]
BLOCK_DEFAULT_ACTIONS = {"dispatch_matching": "match"}
AUTHORED_BY = "codewhale exec"


def _split_candidates(suburb: str, weekday: str, start: int, end: int
                      ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(available, excluded) for every active contractor serving the suburb."""
    available: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for row in domain_rules.serving_contractors(suburb):
        reference = str(row.get("reference") or "").strip()
        if not reference:
            continue
        item = {
            "contractor_reference": reference,
            "contractor_name": row.get("contractor_name"),
            "capacity": int(row.get("capacity") or 1),
            "service_areas": domain_rules.contractor_service_areas(row),
            "service_area_match": True,
        }
        covered = domain_rules.schedule_covers(reference, weekday, start, end) if weekday else None
        if covered is True:
            item["available"] = True
            item["schedule_checked"] = True
            available.append(item)
            continue
        item["available"] = False
        item["schedule_checked"] = covered is not None
        item["reason"] = (
            "published schedule does not cover the slot"
            if covered is False else "no published schedule on file"
        )
        excluded.append(item)
    return available, excluded


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "match")
    booking = str(data.get("booking_reference") or reference)
    suburb = str(data.get("suburb") or "").strip()
    booking_date = str(data.get("booking_date") or "").strip()
    weekday = domain_rules.weekday_of(booking_date)
    start = domain_rules.minutes(data.get("start_time"))
    distance = domain_rules.as_number(data.get("distance_km")) or 0.0
    skills = domain_rules.split_areas(data.get("required_skills"))
    service = domain_rules.service_minutes()

    if start is None:
        return fail("start_time must be a clock value", error_kind="validation_error",
                    rejected_field="start_time")
    start, end, _ = domain_rules.shift_window(start, None, service)

    job = execute(
        "dispatch_matching",
        {
            "job_id": booking,
            "required_skills": skills,
            "location": {"suburb": suburb},
            "distance_km": distance,
        },
        action="register_job",
    )
    if block_failed(job):
        return fail(refusal_text(job))

    candidates, excluded = _split_candidates(suburb, weekday, start, end)
    if not candidates:
        return ok({
            "booking_reference": booking,
            "suburb": suburb,
            "booking_date": booking_date,
            "weekday": weekday,
            "matched": False,
            "reason": (
                "no active contractor is available for that suburb and slot"
                if excluded else "no active contractor serves that suburb"
            ),
            "candidates": [],
            "ranking": [],
            "excluded": excluded,
            "authority": {
                "label": "procedure", "layer": 4,
                "basis": "suburb service-area filter and published-schedule availability",
            },
        })

    steps: List[Dict[str, Any]] = [{
        "action": "register_job",
        "input": {
            "job_id": booking,
            "required_skills": skills,
            "location": {"suburb": suburb},
            "distance_km": distance,
        },
    }]
    for candidate in candidates:
        steps.append({
            "action": "register_worker",
            "input": {
                "worker_id": candidate["contractor_reference"],
                "skills": [],
                "location": {"suburb": suburb},
                "capacity": candidate["capacity"],
                "active": True,
            },
        })
    steps.append({"action": "match", "input": {"job_id": booking}})

    ranked = execute_sequence("dispatch_matching", steps)
    if block_failed(ranked):
        return fail(refusal_text(ranked))

    scores = {
        str(item.get("worker_id")): item
        for item in (ranked.get("candidates") or [])
        if isinstance(item, dict)
    }
    for candidate in candidates:
        scored = scores.get(candidate["contractor_reference"]) or {}
        candidate["score"] = scored.get("score")
        candidate["components"] = scored.get("components")
        candidate["distance_km"] = distance

    # Every candidate here is available for the slot; the block's score is
    # the ordering, and the contractor reference breaks a tie so the answer
    # is deterministic for any input.
    ranking = sorted(
        candidates,
        key=lambda item: (
            -(item.get("score") if item.get("score") is not None else 0.0),
            float(item.get("distance_km") or 0.0),
            item["contractor_reference"],
        ),
    )
    for index, candidate in enumerate(ranking, start=1):
        candidate["rank"] = index
        reasons = ["suburb is an active service area",
                   "published schedule covers the slot"]
        if candidate.get("score") is not None:
            reasons.append("dispatch score %.4f" % float(candidate["score"]))
        candidate["explanation"] = reasons

    return ok({
        "booking_reference": booking,
        "suburb": suburb,
        "booking_date": booking_date,
        "weekday": weekday,
        "slot": {"start": domain_rules.clock(start), "end": domain_rules.clock(end)},
        "required_skills": skills,
        "matched": bool(ranking),
        "candidates": ranking,
        "ranking": ranking,
        "excluded": excluded,
        "authority": {"label": "certified", "layer": 1, "basis": "dispatch_matching/match"},
    })
