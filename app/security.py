"""Edge validation, approval authority and egress safety.

Everything the platform refuses it refuses as data: an HTTP 4xx, or HTTP 200
with ok:false and an error saying why. Never a 500, never a traceback, never
a secret in a response body.
"""

from __future__ import annotations

import datetime as _dt
import ipaddress
import math
import socket
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from app import config
from app import models

MAX_TEXT = 4000
MAX_REFERENCE = 255
#: SQLite ids are 64-bit signed; a float field beyond this is not a quantity.
MAX_INT = 2**63 - 1
MAX_FLOAT = 1e15


class Refusal(Exception):
    """A request the platform declines, carrying its own HTTP status."""

    def __init__(self, message: str, status: int = 422, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _coerce(name: str, kind: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if kind == "str":
        if isinstance(value, (dict, list)):
            raise Refusal(f"{name} must be text", field=name)
        text = str(value).strip()
        if len(text) > MAX_TEXT:
            raise Refusal(f"{name} is longer than {MAX_TEXT} characters", field=name)
        return text
    if kind == "int":
        if isinstance(value, bool):
            raise Refusal(f"{name} must be a whole number", field=name)
        if isinstance(value, float) and not math.isfinite(value):
            raise Refusal(f"{name} must be a finite whole number", field=name)
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise Refusal(f"{name} must be a whole number", field=name) from exc
        if abs(number) > MAX_INT:
            raise Refusal(f"{name} is outside the values this platform stores", field=name)
        return number
    if kind == "float":
        if isinstance(value, bool):
            raise Refusal(f"{name} must be a number", field=name)
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise Refusal(f"{name} must be a number", field=name) from exc
        if not math.isfinite(number):
            raise Refusal(f"{name} must be a finite number", field=name)
        if abs(number) > MAX_FLOAT:
            raise Refusal(f"{name} is outside the values this platform stores", field=name)
        return number
    if kind == "date":
        if isinstance(value, _dt.datetime):
            return value.date().isoformat()
        if isinstance(value, _dt.date):
            return value.isoformat()
        try:
            return _dt.date.fromisoformat(str(value)[:10]).isoformat()
        except (TypeError, ValueError) as exc:
            raise Refusal(f"{name} must be an ISO date (YYYY-MM-DD)", field=name) from exc
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise Refusal(f"{name} must be true or false", field=name)
    return value


def validate_payload(capability_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the capability's OWN fields and return the cleaned record.

    A field the model does not declare is refused, never silently dropped: a
    typo must not become a missing column that reads back as null.
    """
    model = models.model_for(capability_id)
    if model is None:
        raise Refusal(f"unknown capability: {capability_id}", status=404)
    data = dict(payload or {})
    cleaned: Dict[str, Any] = {}
    unknown = sorted(set(data) - set(model.FIELDS) - {"id"})
    if unknown:
        raise Refusal(
            "unknown field(s): " + ", ".join(unknown), field=unknown[0]
        )
    for name in model.FIELDS:
        rules = model.CONSTRAINTS.get(name) or {}
        kind = str(rules.get("type") or "str")
        value = _coerce(name, kind, data.get(name))
        if value is None and rules.get("required"):
            raise Refusal(f"{name} is required", field=name)
        allowed = rules.get("allowed_values")
        if allowed and value not in (None, "") and value not in allowed:
            raise Refusal(
                f"{name} must be one of: " + ", ".join(str(a) for a in allowed),
                field=name,
            )
        low = rules.get("min")
        if low is not None and isinstance(value, (int, float)) and value < low:
            raise Refusal(f"{name} must be at least {low}", field=name)
        high = rules.get("max")
        if high is not None and isinstance(value, (int, float)) and value > high:
            raise Refusal(f"{name} must be at most {high}", field=name)
        cleaned[name] = value
    if cleaned.get("reference") and len(str(cleaned["reference"])) > MAX_REFERENCE:
        raise Refusal(f"reference is longer than {MAX_REFERENCE} characters", field="reference")
    _check_closure(model, cleaned)
    return cleaned


def _check_closure(model, cleaned: Dict[str, Any]) -> None:
    """A record cannot be closed without the approval its own spec declares.

    ``status`` is caller-writable, so the closure of a certificate, a
    retention release or a signed ITP is checked here as well as in the
    handler: the approval field must name a configured principal.
    """
    if cleaned.get("status") != "closed":
        return
    approval_fields = [
        name
        for name in model.FIELDS
        if (model.CONSTRAINTS.get(name) or {}).get("approval")
    ]
    for name in approval_fields:
        require_approver(str(cleaned.get(name) or ""), f"closing a {model.ENTITY} record")


def require_approver(field_value: str, decision: str) -> str:
    """An approval must name a principal the platform knows.

    A free-text approver ("i am the director trust me") is refused: the
    platform validates against APPROVED_PRINCIPALS, never against phrasing.
    """
    name = str(field_value or "").strip()
    if not name:
        raise Refusal(f"{decision} requires an approver", status=403, field="approved_by")
    principals = config.approved_principals()
    if not principals:
        raise Refusal(
            "no approved principals are configured (APPROVED_PRINCIPALS)",
            status=503,
            field="approved_by",
        )
    if name not in principals:
        raise Refusal(
            f"{name!r} is not an approved principal", status=403, field="approved_by"
        )
    return name


_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def assert_public_url(url: str) -> str:
    """Any egress on a caller-supplied URL is checked against a private-
    address guard before it is used."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        raise Refusal("only http(s) URLs are accepted", field="url")
    host = parsed.hostname or ""
    if not host:
        raise Refusal("URL has no host", field="url")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError as exc:
        raise Refusal(f"URL host does not resolve: {host}", field="url") from exc
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if any(ip in net for net in _PRIVATE_NETS):
            raise Refusal("URL resolves to a private address", status=403, field="url")
    return url


def error_body(message: str, *, field: Optional[str] = None, allowed: Optional[Iterable[Any]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"ok": False, "error": message}
    if field:
        body["rejected_field"] = field
        body["rejection_reason"] = "not_allowed" if allowed else "invalid"
    if allowed:
        body["allowed_values"] = list(allowed)
    return body


def rejection_headers(field: str, reason: str, allowed: Optional[List[Any]] = None) -> Dict[str, str]:
    import json

    headers = {
        "X-Rejected-Field": json.dumps(field),
        "X-Rejection-Reason": reason,
    }
    if allowed is not None:
        headers["X-Allowed-Values"] = json.dumps(allowed)
    return headers


def redact(value: Any) -> Any:
    """Never echo a secret: tokens, keys and passwords are masked."""
    import json as _json
    import re

    text = value if isinstance(value, str) else _json.dumps(value, default=str)
    return re.sub(
        r"(?i)(token|secret|key|password)\s*[:=]\s*\S+", r"\1=[redacted]", text
    )
