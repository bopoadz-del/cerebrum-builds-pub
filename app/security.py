"""Edge security: authentication, tenant scoping, payload validation, authz.

Three things happen here and nowhere else on the request path:

* authentication -- a bearer token resolves to one tenant (401 otherwise);
* validation -- a missing required field is 422 naming it, a value outside a
  declared vocabulary is 422 naming the field and the accepted values, and a
  numeric bound is enforced the same way;
* authorization -- each capability declares who may write it, and a missing
  declaration fails closed.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Type

from fastapi import HTTPException, Request

from app.tenancy import PROGRAM_ROLES, Principal, TenantError, resolve_tenant

WRITE_ROLES = PROGRAM_ROLES


def authenticate(headers: Optional[Mapping[str, str]]) -> Principal:
    try:
        return resolve_tenant(headers)
    except TenantError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def principal_from_request(request: Request) -> Principal:
    return authenticate(request.headers)


def require_write(principal: Principal) -> None:
    if not principal.can_write():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "this principal has no write role on the programme",
            },
        )


def validate_payload(cls: Type[Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate at the edge against the capability's declared contract."""
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    for name in getattr(cls, "FIELDS", []):
        rule = constraints.get(name) or {}
        value = payload.get(name)
        present = value is not None and not (isinstance(value, str) and value == "")
        if rule.get("required") and not present:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "validation_error",
                    "rejected_field": name,
                    "rejection_reason": "missing_required",
                    "message": f"{name} is required",
                },
            )
        if not present:
            continue
        allowed = rule.get("allowed_values")
        if allowed and value not in allowed:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "validation_error",
                    "rejected_field": name,
                    "rejection_reason": "not_allowed",
                    "allowed_values": list(allowed),
                    "message": f"{name} must be one of: {', '.join(map(str, allowed))}",
                },
            )
        low, high = rule.get("min"), rule.get("max")
        if low is not None or high is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = None
            if numeric is None or (low is not None and numeric < low) or (
                high is not None and numeric > high
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "validation_error",
                        "rejected_field": name,
                        "rejection_reason": "out_of_range",
                        "message": f"{name} must be between {low} and {high}",
                    },
                )
    return payload


#: Which authenticated roles may create records in each capability. A
#: learner writes their own sessions and submissions; the registrar enrols
#: and administers tracks; faculty grade; reviewers return capstone verdicts.
CAPABILITY_WRITE_ROLES: Dict[str, tuple[str, ...]] = {
    "track_loader": ("Program Director", "Registrar", "Faculty"),
    "enrolment_and_calendar": ("Program Director", "Registrar"),
    "faculty_session": ("Program Director", "Registrar", "Faculty", "Learner"),
    "memo_grading": ("Program Director", "Faculty"),
    "gradebook_and_transcript": ("Program Director", "Registrar", "Faculty"),
    "defense_and_capstone": ("Program Director", "Registrar", "Faculty", "Reviewer"),
    "track_admin": ("Program Director", "Registrar"),
    "reading_and_case_library": ("Program Director", "Registrar", "Faculty", "Learner"),
}


def require_capability_write(principal: Principal, capability_id: str) -> None:
    """Authorize a write against the role matrix for this capability.

    A missing entry fails closed: a new capability is not writable until an
    operator declares who may write it.
    """
    allowed = CAPABILITY_WRITE_ROLES.get(str(capability_id))
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "no write policy for this capability"},
        )
    if not principal.has_role(*allowed):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "role(s) %s may not write %s"
                % (", ".join(principal.roles) or "(none)", capability_id),
            },
        )
