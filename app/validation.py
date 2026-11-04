"""Payload validation: the contract a capability's model declares, enforced.

One module decides what a well-formed record is, so the route, the handlers
and the harness cannot disagree: a field declared ``required`` is refused when
absent, a declared vocabulary refuses an unlisted value, and a declared type,
format or bound is checked rather than assumed. Rejections are returned as
DATA (field, reason, allowed values) so a caller can correct the payload
instead of guessing from prose.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, List, Optional, Tuple

RESERVED_FIELDS = frozenset({"id", "tenant_id", "created_at", "updated_at"})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TYPE_ALIASES = {
    "str": "str",
    "string": "str",
    "text": "str",
    "int": "int",
    "integer": "int",
    "long": "int",
    "float": "float",
    "number": "float",
    "decimal": "float",
    "money": "float",
    "quantity": "float",
    "bool": "bool",
    "boolean": "bool",
    "date": "date",
    "datetime": "datetime",
    "time": "time",
    "email": "email",
}


def declared_type(spec: Dict[str, Any]) -> str:
    raw = str(spec.get("type") or "str").strip().lower()
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|") if p.strip() and p.strip() != "none"]
        raw = parts[0] if parts else "str"
    return TYPE_ALIASES.get(raw, "str")


def _reject(field: str, reason: str, message: str, allowed: Optional[List[Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"field": field, "reason": reason, "message": message}
    if allowed is not None:
        out["allowed"] = list(allowed)
    return out


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _coerce(spec: Dict[str, Any], value: Any) -> Tuple[Any, Optional[str]]:
    """Return (value, error_reason). Never invents a value for a missing one."""
    kind = declared_type(spec)
    if kind == "str" or kind == "email":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value), None
        if not isinstance(value, str):
            return value, "wrong_type"
        return value, None
    if kind == "int":
        if isinstance(value, bool):
            return value, "wrong_type"
        if isinstance(value, int):
            return value, None
        if isinstance(value, float) and value.is_integer():
            return int(value), None
        if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
            return int(value.strip()), None
        return value, "wrong_type"
    if kind == "float":
        if isinstance(value, bool):
            return value, "wrong_type"
        if isinstance(value, (int, float)):
            return float(value), None
        if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value.strip()):
            return float(value.strip()), None
        return value, "wrong_type"
    if kind == "bool":
        if isinstance(value, bool):
            return value, None
        return value, "wrong_type"
    return value, None


def _check_format(fmt: str, value: str) -> bool:
    fmt = (fmt or "").strip().lower()
    if fmt == "email":
        return bool(_EMAIL_RE.match(value.strip()))
    if fmt == "date":
        try:
            _dt.date.fromisoformat(value.strip())
        except ValueError:
            return False
        return True
    if fmt in ("datetime", "timestamp", "iso8601"):
        try:
            _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return False
        return True
    if fmt == "time":
        try:
            _dt.time.fromisoformat(value.strip())
        except ValueError:
            return False
        return True
    return True


def validate_payload(model_cls, payload: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Validate ``payload`` against ``model_cls``.

    Returns (accepted values for every declared field, violations). Violations
    are ordered field-first so a caller converges in one round trip.
    """
    if not isinstance(payload, dict):
        return {}, [_reject("", "not_an_object", "a JSON object is required")]
    if model_cls is None:
        return {}, [_reject("", "unknown_capability", "unknown capability")]

    constraints: Dict[str, Dict[str, Any]] = getattr(model_cls, "CONSTRAINTS", {}) or {}
    values: Dict[str, Any] = {}
    violations: List[Dict[str, Any]] = []

    for name in getattr(model_cls, "FIELDS", []) or []:
        spec = constraints.get(name) or {}
        present = name in payload
        raw = payload.get(name)

        if not present or (isinstance(raw, str) and raw == ""):
            if spec.get("required"):
                violations.append(
                    _reject(name, "missing_required", f"{name} is required")
                )
                continue
            if present:
                values[name] = raw if raw == "" else None
            continue

        if _is_blank(raw):
            if spec.get("required"):
                violations.append(_reject(name, "missing_required", f"{name} is required"))
            continue

        coerced, error = _coerce(spec, raw)
        if error:
            violations.append(
                _reject(
                    name,
                    error,
                    f"{name} must be a {declared_type(spec)}",
                    spec.get("allowed_values"),
                )
            )
            continue

        allowed = spec.get("allowed_values")
        if allowed and coerced not in allowed:
            violations.append(
                _reject(name, "not_allowed", f"{name} must be one of: " + ", ".join(map(str, allowed)), allowed)
            )
            continue

        fmt = str(spec.get("format") or "").lower()
        if fmt and isinstance(coerced, str) and not _check_format(fmt, coerced):
            violations.append(
                _reject(name, "bad_format", f"{name} must be a {fmt}", None)
            )
            continue

        if isinstance(coerced, (int, float)) and not isinstance(coerced, bool):
            low, high = spec.get("min"), spec.get("max")
            if low is not None and coerced < low:
                violations.append(
                    _reject(name, "out_of_range", f"{name} must be >= {low}", None)
                )
                continue
            if high is not None and coerced > high:
                violations.append(
                    _reject(name, "out_of_range", f"{name} must be <= {high}", None)
                )
                continue

        limit = spec.get("max_length")
        if limit is not None and isinstance(coerced, str) and len(coerced) > int(limit):
            violations.append(
                _reject(name, "too_long", f"{name} must be at most {limit} characters", None)
            )
            continue

        values[name] = coerced

    for key in payload:
        if key in RESERVED_FIELDS:
            violations.append(
                _reject(key, "reserved_field", f"{key} is set by the platform, not the caller")
            )

    return values, violations


def sample_value(spec: Dict[str, Any]) -> Any:
    """A value that satisfies every constraint the field declares."""
    allowed = spec.get("allowed_values")
    if allowed:
        for candidate in allowed:
            if str(candidate).strip().lower() in ("mcp", "slack", "webhook", "email"):
                return candidate
        return allowed[0]
    kind = declared_type(spec)
    fmt = str(spec.get("format") or "").lower()
    if kind == "email" or fmt == "email":
        return "guest@example.com"
    if kind == "date" or fmt == "date":
        return "2026-09-03"
    if kind == "datetime" or fmt in ("datetime", "timestamp", "iso8601"):
        return "2026-09-03T10:00:00"
    if kind == "time" or fmt == "time":
        return "10:00:00"
    if kind in ("int", "float"):
        low, high = spec.get("min"), spec.get("max")
        if low is not None:
            if low <= 0 and (high is None or high >= 1):
                return 1 if kind == "int" else 1.0
            return low
        if high is not None:
            return high if high < 1 else (1 if kind == "int" else 1.5)
        return 1 if kind == "int" else 1.5
    if kind == "bool":
        return True
    return "sample"


def sample_for_model(model_cls) -> Dict[str, Any]:
    constraints: Dict[str, Dict[str, Any]] = getattr(model_cls, "CONSTRAINTS", {}) or {}
    out: Dict[str, Any] = {}
    for name in getattr(model_cls, "FIELDS", []) or []:
        spec = dict(constraints.get(name) or {})
        out[name] = sample_value(spec)
    return out
