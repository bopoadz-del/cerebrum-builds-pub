"""Authentication, tenancy binding and declared-field validation.

Every /v1 route refuses an unauthenticated caller with 401. A payload that
omits a required field, carries an unknown field, uses a value outside a
declared vocabulary, violates a declared format or bound, or exceeds the
field size ceiling is refused with 422 naming the field. The tenant comes
from the bearer token, never from the payload.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time as _time
from typing import Any, Dict

from fastapi import HTTPException, Request

MAX_FIELD_CHARS = 20000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def require_platform_token(request: Request) -> Any:
    import app.tenancy as tenancy

    try:
        return tenancy.resolve_tenant(request.headers)
    except tenancy.TenantRefused:
        try:
            from app import observability

            client = getattr(getattr(request, "client", None), "host", None) or "unknown"
            if observability.failed_auth_limited(str(client)):
                raise HTTPException(status_code=429, detail="too_many_requests")
        except ImportError:
            pass
        raise HTTPException(status_code=401, detail="authentication_required")


def require_read_token(request: Request) -> Any:
    return require_platform_token(request)


def _format_refusal(name: str, rules: Dict[str, Any], value: Any) -> str | None:
    fmt = str((rules or {}).get("format") or "").strip().lower()
    if not fmt or not isinstance(value, str) or value == "":
        return None
    if fmt == "email":
        if not _EMAIL_RE.match(value.strip()):
            return name + " must be an email address"
        return None
    if fmt == "date":
        try:
            date.fromisoformat(value.strip()[:10])
        except ValueError:
            return name + " must be a date (YYYY-MM-DD)"
        return None
    if fmt in ("datetime", "timestamp", "iso8601"):
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return name + " must be an ISO-8601 datetime"
        return None
    if fmt == "time":
        try:
            _time.fromisoformat(value.strip())
        except ValueError:
            return name + " must be a time (HH:MM:SS)"
        return None
    if fmt in ("identifier", "slug"):
        text = value.strip()
        if not _IDENTIFIER_RE.match(text) or ".." in text:
            return name + " must be an identifier (letters, digits, dot, colon, hyphen, underscore)"
        return None
    return None


def reject_invalid_payload(capability_id: str, payload: Dict[str, Any] | None) -> None:
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    if cls is None:
        raise HTTPException(status_code=422, detail="unknown capability")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="payload must be an object")
    fields = list(getattr(cls, "FIELDS", []) or [])
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    unknown = sorted(k for k in payload if k not in fields)
    if unknown:
        raise HTTPException(status_code=422, detail="unknown field(s): " + ", ".join(unknown))
    for name in fields:
        rules = constraints.get(name) or {}
        value = payload.get(name)
        if rules.get("required") and (name not in payload or value in (None, "")):
            raise HTTPException(status_code=422, detail="Missing required field: " + name)
        if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
            raise HTTPException(
                status_code=422,
                detail=name + " exceeds " + str(MAX_FIELD_CHARS) + " characters",
            )
    for name, rules in constraints.items():
        if name not in payload:
            continue
        refusal = _format_refusal(name, rules, payload[name])
        if refusal:
            raise HTTPException(status_code=422, detail=refusal)
        allowed = rules.get("allowed_values")
        if allowed is not None and payload[name] not in allowed:
            raise HTTPException(
                status_code=422,
                detail=name + " must be one of: " + ", ".join(str(v) for v in allowed),
            )
        low, high = rules.get("min"), rules.get("max")
        value = payload[name]
        if low is None and high is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            limits = []
            if low is not None:
                limits.append("at least " + str(low))
            if high is not None:
                limits.append("at most " + str(high))
            raise HTTPException(
                status_code=422,
                detail=name + " must be a number (" + ", ".join(limits) + ")",
            )
        if low is not None and value < low:
            raise HTTPException(status_code=422, detail=name + " is below the minimum " + str(low))
        if high is not None and value > high:
            raise HTTPException(status_code=422, detail=name + " is above the maximum " + str(high))


def reject_reserved_payload_keys(payload: Dict[str, Any] | None) -> None:
    from app import security

    try:
        security.guard_payload(payload or {})
    except security.PayloadRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def approved_principals() -> set:
    raw = (os.environ.get("APPROVED_PRINCIPALS") or "").strip()
    return {item.strip() for item in raw.split(",") if item.strip()}


def reject_unknown_approver(capability_id: str, payload: Dict[str, Any] | None) -> None:
    """A field the spec marks as an approval must name a configured principal."""
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    if cls is None or not isinstance(payload, dict):
        return
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    for name, rules in constraints.items():
        if not rules.get("approval_when"):
            continue
        value = payload.get(name)
        if value in (None, ""):
            continue
        if str(value) not in approved_principals():
            raise HTTPException(
                status_code=403,
                detail=name + " must name an approved principal",
            )
