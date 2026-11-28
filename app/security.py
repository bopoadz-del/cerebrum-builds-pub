"""Request-edge validation helpers.

Authentication is resolved by app.tenancy; this module keeps the route guard
and response redaction in one place so no route invents its own policy.
"""

from __future__ import annotations

from typing import Any, Dict

from app.tenancy import Tenant, Unauthorized, resolve_tenant

RESERVED_FIELDS = frozenset({"action"})


def require_tenant(headers: Any) -> Tenant:
    try:
        return resolve_tenant(headers)
    except Unauthorized as exc:
        raise Unauthorized(str(exc)) from exc


def redact(value: Any, keys=("token", "api_key", "authorization", "password")) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if str(key).lower() in keys else redact(item, keys))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, keys) for item in value]
    return value


def public_error(message: str, **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {"ok": False, "error": str(message)}
    body.update(extra)
    return body
