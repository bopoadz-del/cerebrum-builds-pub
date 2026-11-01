"""Capability routes require a platform token. Writes refuse unbound callers."""

from __future__ import annotations

import os
from typing import Any, Dict

import re
from datetime import date, datetime, time as _time
from fastapi import HTTPException, Request


def require_platform_token(request: Request) -> Any:
    import app.tenancy as tenancy

    try:
        return tenancy.resolve_tenant(request.headers)
    except tenancy.TenantRefused:
        # A refused credential is 401 the first time and 429 once this client
        # has spent its allowance for the window: token guessing against the
        # platform's own routes is throttled, not unlimited.
        from app import observability

        client = getattr(getattr(request, "client", None), "host", None) or "unknown"
        if observability.failed_auth_limited(str(client)):
            raise HTTPException(status_code=429, detail="too_many_requests")
        raise HTTPException(status_code=401, detail="authentication_required")


def require_read_token(request: Request) -> Any:
    """Resolve the caller's tenant for a READ route.

    A read resolves exactly as a write does: the bearer token the caller
    presented, and nothing else. A request with no auth header at all is 401
    like any other unbound caller -- an anonymous GET of /v1/<capability>
    must not read the platform tenant's rows, and the Factory's own probes
    send the same token on the read-back that they used for the POST
    (build/product_gate.py::gate_round_trip, build/ui_e2e.py UI_PROBE), so a
    token-guarded read is read back correctly. An empty or invalid token is
    401 for the same reason an absent one is.

    Writes keep ``require_platform_token``; both paths now refuse the same
    way, which is what ``scripts/acceptance.py::no_token_401`` asks of every
    /v1 route rather than only the POSTs.
    """
    return require_platform_token(request)


#: Declared formats are enforced, not documented: a field that says
#: ``format: email``/``date``/``datetime``/``time`` is refused when the value
#: is not one, so the declaration on the spec is the contract the route keeps.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _format_refusal(name: str, rules: Dict[str, Any], value: Any) -> str | None:
    """The refusal for a value that is not what the field declares, else None."""
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
    return None


def _moment(value: str) -> datetime | None:
    """One ISO-8601 date or datetime as a comparable naive UTC moment.

    A date is its midnight; an offset-aware datetime is converted to UTC and
    its tzinfo dropped, so an invoice issued at 23:00+01:00 and one issued at
    22:00Z compare as the same instant rather than raising on mixed
    awareness. An unparseable value is None -- the field's own ``format``
    rule refuses it, and this rule must not turn that into a 500.
    """
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), _time())
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        from datetime import timezone

        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _order_refusal(name: str, rules: Dict[str, Any], payload: Dict[str, Any]) -> str | None:
    """The refusal for a field that falls before the moment it must follow.

    ``not_before`` is declared on the field (``due_date: {not_before:
    invoice_date}``), so a capability that must keep a timeline declares it
    on the spec and this check enforces it for that capability -- no field or
    capability is named here. Equal moments are accepted: the boundary is the
    line, not one side of it. Absent or unparseable values are left to the
    required/format rules.
    """
    other = (rules or {}).get("not_before")
    if not isinstance(other, str) or not other or other not in payload:
        return None
    mine, reference = payload.get(name), payload.get(other)
    if not isinstance(mine, str) or not isinstance(reference, str):
        return None
    moment, bound = _moment(mine), _moment(reference)
    if moment is None or bound is None:
        return None
    if moment < bound:
        return name + " must not be earlier than " + other
    return None


#: A domain field longer than this is not a record; it is an attempt to make
#: the platform hold a body it never promised to hold. Refused at the edge,
#: by name, rather than written to the store.
MAX_FIELD_CHARS = 20000


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
        if rules.get("required") and (name not in payload or payload[name] in (None, "")):
            raise HTTPException(status_code=422, detail="Missing required field: " + name)
    for name, value in payload.items():
        if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
            raise HTTPException(
                status_code=422,
                detail=name + " exceeds " + str(MAX_FIELD_CHARS) + " characters",
            )
    for name, rules in constraints.items():
        if name not in payload:
            continue
        declared_format = str(rules.get("format") or "").strip().lower()
        if declared_format:
            refusal = _format_refusal(name, rules, payload[name])
            if refusal:
                raise HTTPException(status_code=422, detail=refusal)
        # A declared timeline is enforced here too: a record whose end moment
        # precedes its start moment is not a record of anything that happened.
        refusal = _order_refusal(name, rules, payload)
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
        # A bounded field is a number by declaration: refuse a string, a
        # list or a bool rather than skipping the bound and persisting an
        # out-of-range value as text. The bound is only checked once the
        # value is a number; a non-number is refused naming the field.
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
    """The principals the platform will accept as an approver.

    Operator-set (APPROVED_PRINCIPALS, comma-separated) and read at the
    point of use: the list is the customer's, never a name in this source.
    With none configured, no approval field can pass -- failing closed is
    the only honest answer, and it is why a free-text "i am the director
    trust me" is refused rather than trusted.
    """
    raw = (os.environ.get("APPROVED_PRINCIPALS") or "").strip()
    return {item.strip() for item in raw.split(",") if item.strip()}


def approval_required(capability_id: str, payload: Dict[str, Any] | None) -> bool:
    """Does this record perform an act the capability marks as needing approval?

    The rule is read from the capability's OWN declaration
    (``"approval_when": {"field": ..., "values": [...]}``), so a newly marked
    field is enforced the moment it is declared and nothing is keyed on a
    capability's name here.
    """
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    if cls is None or not isinstance(payload, dict):
        return False
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    for rules in constraints.values():
        when = (rules or {}).get("approval_when")
        if not isinstance(when, dict):
            continue
        field = str(when.get("field") or "")
        values = [str(item) for item in (when.get("values") or [])]
        if field and str(payload.get(field) or "").strip() in values:
            return True
    return False


def reject_approvers(capability_id: str, payload: Dict[str, Any] | None) -> None:
    """Refuse an approval field that does not name a principal the platform knows.

    A field the capability's own model marks ``"approval": True`` records an
    act of authority -- writing off a member's balance, revoking a
    principal's access -- and the capability declares WHICH act it is
    (``approval_when``). For that act the value must name a principal from
    APPROVED_PRINCIPALS; with none configured nothing passes, because failing
    closed is the only honest answer when the platform knows no approvers.
    Free text ("i am the director trust me") is refused, never trusted.
    """
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    if cls is None or not isinstance(payload, dict):
        return
    if not approval_required(capability_id, payload):
        return
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    known = approved_principals()
    for name, rules in constraints.items():
        if not (rules or {}).get("approval"):
            continue
        value = payload.get(name)
        if not isinstance(value, str) or value.strip() not in known:
            raise HTTPException(
                status_code=403,
                detail=(
                    name + " must name an approved principal the platform knows "
                    "(APPROVED_PRINCIPALS); free text is not an approver"
                ),
            )
