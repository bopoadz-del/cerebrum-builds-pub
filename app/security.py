"""Edge security: authentication, authorisation and the refusal shapes.

Every /v1 route authenticates the request at the edge and answers 401 when it
cannot; nothing is served because a caller "probably" belongs here. A record
that belongs to another tenant answers 404 -- never 403 -- so existence never
leaks across tenants.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, Request, status

from app import tenancy

WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


def principal_from_request(request: Request):
    """The authenticated principal, or a 401 that names authentication.

    A refused credential is rate limited per client address so token guessing
    is bounded; a valid request is never throttled by this limiter.
    """
    from app import observability

    auth = request.headers.get("authorization")
    principal = tenancy.authenticate(auth)
    if principal is None:
        client = request.client.host if request.client else "unknown"
        if not observability.LIMITER.allow(client):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many authentication attempts",
                headers=dict(WWW_AUTHENTICATE),
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers=dict(WWW_AUTHENTICATE),
        )
    return principal


def require_principal(request: Request):
    """FastAPI dependency alias used by the routers."""
    return principal_from_request(request)


def optional_principal(request: Request):
    """The principal when a credential was presented, else None.

    A route that serves public metadata (the capability catalogue) or operates
    on text the caller supplied uses this. A presented credential is still
    verified; an absent one yields no tenant, so nothing tenant-scoped is read.
    """
    if not request.headers.get("authorization"):
        return None
    return principal_from_request(request)


def not_found(resource: str = "record") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def rejected(violation: Dict[str, Any]) -> Dict[str, Any]:
    """The refusal body a caller (and the harness) can read as data."""
    body: Dict[str, Any] = {
        "ok": False,
        "error": violation.get("message") or "the payload was refused",
        "rejected_field": violation.get("field") or "",
        "rejection_reason": violation.get("reason") or "",
    }
    if violation.get("allowed") is not None:
        body["allowed_values"] = list(violation["allowed"])
    return body


def rejection_headers(violation: Dict[str, Any]) -> Dict[str, str]:
    import json

    headers = {
        "X-Rejected-Field": json.dumps(violation.get("field") or ""),
        "X-Rejection-Reason": str(violation.get("reason") or ""),
    }
    if violation.get("allowed") is not None:
        headers["X-Allowed-Values"] = json.dumps(list(violation["allowed"]))
    return headers
