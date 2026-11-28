"""Admin/ops back office over contractors, suburbs, bookings and disputes.

The operator sees measured oversight counts (from the tenant's own records)
and maintains the managed suburb catalogue that contractor onboarding selects
from.  Disputes run through the vendored dispute_resolution lifecycle: open,
escalate, resolve, status; the dashboard block renders the oversight surface.

SCALE: one dispute or catalogue operation per call.
READS: caller fields, the tenant's contractor/booking/schedule/catalogue rows.
WRITES: the outcome in the response; the route persists the ops record and the
        catalogue row the handler computed.
NEVER: a dispute the claimant is not party to, a state the block refuses, or a
       suburb the operator did not name.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute, execute_sequence

CAPABILITY_ID = "ops_back_office"
ENTITY = "ops_back_office"
BLOCK_IDS = ["dashboard", "dispute_resolution"]
BLOCK_DEFAULT_ACTIONS = {"dashboard": "render", "dispute_resolution": "open"}
AUTHORED_BY = "codewhale exec"

DISPUTE_ACTIONS = ("open", "escalate", "resolve", "status")
RESOLUTIONS = ("released", "refunded", "dismissed")


def _triage(state: str) -> str:
    return {"open": "new", "in_progress": "active", "closed": "archived"}.get(
        str(state or "").casefold(), "new"
    )


def _catalogue_summary() -> Dict[str, Any]:
    catalogue = domain_rules.suburb_catalogue()
    active = [row for row in catalogue
              if domain_rules.truthy(row.get("active"), default=True)]
    pending = []
    seen = set()
    for row in domain_rules.tenant_records(domain_rules.CONTRACTOR_ENTITY):
        for area in domain_rules.split_areas(row.get("pending_suburbs")):
            key = domain_rules.normalise_area(area)
            if key and key not in seen:
                seen.add(key)
                pending.append({
                    "suburb": area,
                    "contractor_reference": row.get("reference"),
                })
    return {
        "catalogue_size": len(catalogue),
        "active_suburbs": len(active),
        "active": [row.get("suburb") for row in active],
        "pending_proposals": pending,
    }


def _oversight(suburb: str) -> Dict[str, Any]:
    contractors = domain_rules.tenant_records(domain_rules.CONTRACTOR_ENTITY)
    schedules = domain_rules.tenant_records(domain_rules.SCHEDULE_ENTITY)
    bookings = domain_rules.tenant_records(domain_rules.BOOKING_ENTITY)
    disputes = domain_rules.tenant_records("ops_back_office")
    catalogue = _catalogue_summary()
    wanted = domain_rules.normalise_area(suburb)
    suburbs = {domain_rules.normalise_area(name) for name in catalogue["active"]}
    if wanted:
        contractors = [
            row for row in contractors
            if wanted in {domain_rules.normalise_area(a)
                          for a in domain_rules.split_areas(row.get("service_suburbs"))}
        ]
    return {
        "suburb": suburb or None,
        "contractors": len(contractors),
        "suburbs": catalogue["active_suburbs"],
        "catalogue_size": catalogue["catalogue_size"],
        "schedules": len(schedules),
        "bookings": len(bookings),
        "disputes": len(disputes),
        "active_suburbs": catalogue["active"],
        "pending_proposals": catalogue["pending_proposals"],
    }


def _dispute(reference: str, booking: str, claimant: str, claim_type: str,
             action: str, resolution: str, notes: str) -> Dict[str, Any]:
    opened = {
        "action": "open",
        "input": {
            "dispute_id": reference,
            "task_id": booking,
            "claimant": claimant,
            "claim_type": claim_type,
            "parties": [claimant, "counterparty"],
            "step": 0,
        },
    }
    steps: List[Dict[str, Any]] = [opened]
    if action == "escalate":
        steps.append({"action": "escalate", "input": {"dispute_id": reference}})
    elif action == "resolve":
        steps.append({
            "action": "resolve",
            "input": {
                "dispute_id": reference,
                "platform": "platform",
                "resolution": resolution,
                "reason": notes or "operator decision",
            },
        })
    elif action == "status":
        steps.append({"action": "status", "input": {"dispute_id": reference}})
    return execute_sequence("dispute_resolution", steps)


def _suburb_entry(data: Dict[str, Any]) -> Dict[str, Any]:
    suburb = " ".join(str(data.get("suburb") or "").split())
    active = domain_rules.truthy(data.get("suburb_active"), default=True)
    region = " ".join(str(data.get("region") or "").split()) or None
    return {
        "reference": "suburb:" + domain_rules.normalise_area(suburb),
        "status": "open" if active else "closed",
        "notes": str(data.get("resolution_notes") or data.get("notes") or ""),
        "suburb": suburb,
        "region": region,
        "active": bool(active),
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("dispute_reference") or ("dispute-" + str(data.get("reference") or "ops")))
    booking = str(data.get("booking_reference") or data.get("reference") or "")
    claimant = str(data.get("claimant") or "operator").strip() or "operator"
    claim_type = str(data.get("claim_type") or "booking").strip() or "booking"
    suburb = str(data.get("suburb") or "").strip()
    notes = str(data.get("resolution_notes") or "").strip()
    maintain = domain_rules.truthy(data.get("maintain_suburbs"), default=False)
    action = str(data.get("dispute_action") or "").strip().casefold()
    if action not in DISPUTE_ACTIONS:
        action = "open"
    resolution = str(data.get("resolution") or "released").strip().casefold()
    if resolution not in RESOLUTIONS:
        return fail("resolution must be one of %s" % (list(RESOLUTIONS),),
                    error_kind="validation_error", rejected_field="resolution")

    view = execute(
        "dashboard",
        {
            "user_id": str(data.get("reference") or "operator"),
            "surfaces": ["contractors", "suburbs", "bookings", "disputes"],
            "suburb": suburb or None,
        },
        action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
    )
    if block_failed(view):
        return fail(refusal_text(view))
    widgets = view.get("widgets") or []
    catalogue = _catalogue_summary()

    if maintain:
        entry = _suburb_entry(data)
        if not entry["suburb"]:
            return fail("suburb must name the suburb to maintain",
                        error_kind="validation_error", rejected_field="suburb")
        if len(entry["suburb"]) > 120:
            return fail("suburb is too long", error_kind="validation_error",
                        rejected_field="suburb")
        # The ops surface drives both declared blocks on every operation: the
        # catalogue request is still opened on the dispute ledger so the
        # back office has one audit trail for every ops action.
        opened_for_catalogue = execute(
            "dispute_resolution",
            {
                "dispute_id": reference,
                "task_id": booking,
                "claimant": claimant,
                "claim_type": claim_type,
                "parties": [claimant, "counterparty"],
            },
            action="open",
        )
        if block_failed(opened_for_catalogue):
            return fail(refusal_text(opened_for_catalogue))
        return ok({
            "reference": str(data.get("reference") or reference),
            "status": str(data.get("status") or "open"),
            "notes": str(data.get("notes") or ""),
            "dispute_reference": reference,
            "booking_reference": booking,
            "claimant": claimant,
            "claim_type": claim_type,
            "suburb": entry["suburb"],
            "region": entry["region"],
            "maintain_suburbs": True,
            "suburb_active": entry["active"],
            "catalogue_action": "register" if entry["active"] else "deactivate",
            "catalogue_entry": entry,
            "dispute_state": opened_for_catalogue.get("state", "open"),
            "catalogue_size": catalogue["catalogue_size"],
            "dashboard_widgets": len(widgets),
            "surfaces": [
                {"name": "contractors", "records": len(domain_rules.tenant_records(domain_rules.CONTRACTOR_ENTITY))},
                {"name": "suburbs", "records": catalogue["catalogue_size"]},
                {"name": "bookings", "records": len(domain_rules.tenant_records(domain_rules.BOOKING_ENTITY))},
                {"name": "disputes", "records": len(domain_rules.tenant_records("ops_back_office"))},
            ],
            "pending_proposals": catalogue["pending_proposals"],
            "authority": {"label": "certified", "layer": 3, "basis": "dashboard render + service_suburb catalogue"},
        })

    opened = execute(
        "dispute_resolution",
        {
            "dispute_id": reference,
            "task_id": booking,
            "claimant": claimant,
            "claim_type": claim_type,
            "parties": [claimant, "counterparty"],
        },
        action="open",
    )
    if block_failed(opened):
        return fail(refusal_text(opened))

    dispute = _dispute(reference, booking, claimant, claim_type, action, resolution, notes)
    if block_failed(dispute):
        return fail(refusal_text(dispute))

    oversight = _oversight(suburb)
    return ok({
        "reference": str(data.get("reference") or reference),
        "status": str(data.get("status") or "open"),
        "notes": str(data.get("notes") or ""),
        "dispute_reference": reference,
        "booking_reference": booking,
        "claimant": claimant,
        "claim_type": claim_type,
        "suburb": suburb,
        "region": str(data.get("region") or ""),
        "dispute_action": action,
        "state": dispute.get("state", "open"),
        "triage_state": _triage(data.get("status")),
        "resolution": dispute.get("resolution"),
        "parties": [claimant, "counterparty"],
        "maintain_suburbs": False,
        "suburb_active": None,
        "dashboard_widgets": len(widgets),
        "surfaces": [
            {"name": "contractors", "records": oversight["contractors"]},
            {"name": "suburbs", "records": oversight["suburbs"]},
            {"name": "bookings", "records": oversight["bookings"]},
            {"name": "disputes", "records": oversight["disputes"]},
        ],
        "oversight": oversight,
        "catalogue_size": oversight["catalogue_size"],
        "pending_proposals": oversight["pending_proposals"],
        "authority": {"label": "certified", "layer": 3, "basis": "dispute_resolution + dashboard"},
    })

