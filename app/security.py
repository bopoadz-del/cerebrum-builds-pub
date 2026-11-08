"""Edge validation shared by the HTTP routes.

Authentication is resolved by app.tenancy from the request's bearer token.
Approval fields are validated against the platform's configured principals:
a free-text approver is refused, never trusted.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, Request

from app import tenancy


def require_tenant(request: Request) -> tenancy.Tenant:
    try:
        return tenancy.resolve_tenant(dict(request.headers))
    except tenancy.AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": str(exc), "error_kind": "unauthenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def refusal(field_name: str, reason: str, allowed: Any = None) -> Dict[str, Any]:
    return {
        "rejected_field": field_name,
        "rejection_reason": reason,
        "allowed_values": list(allowed or []),
    }


def check_approver(name: str) -> str:
    candidate = str(name or "").strip()
    if not candidate:
        raise HTTPException(status_code=422, detail=refusal("signed_off_by", "missing_required"))
    if not tenancy.is_approved_principal(candidate):
        raise HTTPException(
            status_code=422,
            detail=refusal("signed_off_by", "not_an_approved_principal", tenancy.approved_principals()),
        )
    return candidate
