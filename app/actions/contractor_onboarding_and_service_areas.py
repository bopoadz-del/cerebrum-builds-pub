"""Contractor onboarding and per-suburb service areas.

A contractor account is a delivery vendor whose service areas are the suburbs
they selected as active.  The vendored vendor_catalog registers the vendor;
the capability validates the profile and decides the activation state an
operator will see.

The contractor owns the selection.  A suburb the contractor picks is an
active service area unless the ops back office has explicitly retired it in
the tenant's managed catalogue.  A suburb the catalogue has not seen yet is
still a working service area and is also raised to ops as a proposal, so the
catalogue catches up with the contractors rather than gating them.

SCALE: one contractor record per call.
READS: caller fields, the tenant's suburb catalogue and own contractor records.
WRITES: the block result in the response; the route persists the record.
NEVER: another tenant's records, a retired catalogue suburb as an active
       area, or an activation the contractor did not ask for.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute

CAPABILITY_ID = "contractor_onboarding_and_service_areas"
ENTITY = "contractor_onboarding_and_service_areas"
BLOCK_IDS = ["vendor_catalog"]
BLOCK_DEFAULT_ACTIONS = {"vendor_catalog": "register_vendor"}
AUTHORED_BY = "codewhale exec"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _contact_channels(email: str, phone: str) -> List[str]:
    """The contact methods the caller actually supplied, by declared field."""
    channels: List[str] = []
    if email:
        channels.append("email")
    if phone:
        channels.append("phone")
    return channels


def _profile_state(active_areas: List[str], retired: List[str],
                   proposed: List[str], active: bool) -> Dict[str, Any]:
    """The activation decision an ops operator reads.

    Every selected suburb is a service area except a catalogue suburb the
    ops back office retired.  Activation therefore depends on the caller's
    own ``active`` flag and on there being at least one usable area; an
    unlisted suburb is usable and is proposed for cataloguing.
    """
    activated = bool(active and active_areas)
    if activated and proposed:
        state = "active_pending_catalogue"
    elif activated:
        state = "active"
    elif retired and not active_areas:
        state = "blocked_retired_suburbs"
    else:
        state = "inactive"
    reasons: List[str] = []
    if not active:
        reasons.append("contractor profile is set inactive")
    if not active_areas:
        reasons.append("no usable service suburb was selected")
    if retired:
        reasons.append("retired catalogue suburb(s) withheld: " + ", ".join(retired))
    return {
        "service_area_count": len(active_areas),
        "active_area_count": len(active_areas) if activated else 0,
        "pending_area_count": len(proposed),
        "retired_area_count": len(retired),
        "activated": activated,
        "onboarding_state": state,
        "activation_blocked_reason": "; ".join(reasons) if reasons else None,
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "contractor").strip() or "contractor"
    name = str(data.get("contractor_name") or reference).strip() or reference
    areas = domain_rules.split_areas(data.get("service_suburbs"))
    if not areas:
        return fail("service_suburbs must name at least one suburb",
                    error_kind="validation_error", rejected_field="service_suburbs")

    email = str(data.get("contact_email") or "").strip()
    if email and not EMAIL_RE.match(email):
        return fail("contact_email is not a valid address",
                    error_kind="validation_error", rejected_field="contact_email")

    capacity = int(data.get("capacity") or 1)
    if capacity < 1:
        return fail("capacity must be at least 1", error_kind="validation_error",
                    rejected_field="capacity")
    active = domain_rules.truthy(data.get("active"), default=True)

    account = domain_rules.contractor_profile(reference)
    if account is not None and str(account.get("status") or "") == "closed":
        return fail("contractor account is closed", error_kind="validation_error",
                    rejected_field="reference")

    catalogue = domain_rules.catalogue_areas(active_only=False)
    active_areas, retired, proposed = domain_rules.partition_selection(areas)
    state = _profile_state(active_areas, retired, proposed, active)
    phone = str(data.get("phone") or "").strip()
    vehicle = str(data.get("vehicle_type") or "").strip()
    channels = _contact_channels(email, phone)

    vendor = execute(
        "vendor_catalog",
        {
            "vendor_id": reference,
            "name": name,
            "categories": ["other"],
            "service_radius_km": max(1, len(active_areas)),
            "active": state["activated"],
            "service_areas": active_areas,
        },
        action=BLOCK_DEFAULT_ACTIONS.get("vendor_catalog"),
    )
    if block_failed(vendor):
        return fail(refusal_text(vendor))

    return ok({
        "reference": reference,
        "status": str(data.get("status") or "open"),
        "notes": str(data.get("notes") or ""),
        "vendor_id": vendor.get("vendor_id", reference),
        "contractor_name": name,
        "contact_email": email,
        "phone": phone,
        "contact_channels": channels,
        "contact_channel_count": len(channels),
        "vehicle_type": vehicle,
        "service_suburbs": ", ".join(active_areas),
        "service_areas": active_areas,
        "pending_areas": proposed,
        "retired_areas": retired,
        "catalogue_size": len(catalogue),
        "catalogue_state": state["onboarding_state"],
        "profile_complete": bool(name and channels and active_areas),
        **state,
        # The activation decision is this capability's own procedure; the
        # vendor registration is the certified block result.  Neither is
        # labelled with a source it did not come from.
        "authority": {
            "label": "procedure",
            "layer": 4,
            "basis": "contractor onboarding activation rule over vendor_catalog/register_vendor",
        },
        "claims": {
            "service_area_count": {
                "value": len(active_areas),
                "basis": "selected suburbs minus retired catalogue suburbs",
                "authority": {"label": "procedure", "layer": 4},
            },
            "pending_area_count": {
                "value": len(proposed),
                "basis": "selected suburbs absent from the ops catalogue",
                "authority": {"label": "procedure", "layer": 4},
            },
            "retired_area_count": {
                "value": len(retired),
                "basis": "selected suburbs the ops catalogue marks inactive",
                "authority": {"label": "procedure", "layer": 4},
            },
            "contact_channel_count": {
                "value": len(channels),
                "basis": "declared contact methods present in this payload",
                "authority": {"label": "procedure", "layer": 4},
            },
            "vendor_id": {
                "value": vendor.get("vendor_id", reference),
                "basis": "vendor_catalog/register_vendor",
                "authority": {"label": "certified", "layer": 1},
            },
        },
    })
