"""One tenant per request, resolved from the authenticated principal.

Tokens come from the deploy environment only: ``PLATFORM_TOKEN`` names the
platform tenant, ``TENANT_TOKENS`` a comma-separated ``token:tenant`` set.
There is no baked token and no fallback: an unset or unknown token is a 401,
never the default tenant.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFAULT_TENANT = "local"


class Unauthenticated(RuntimeError):
    """No principal: every /v1 route refuses with 401."""


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    principal_id: str
    token: str


def _header(headers: Any) -> Optional[str]:
    if headers is None:
        return None
    value = None
    if hasattr(headers, "get"):
        value = headers.get("authorization") or headers.get("Authorization")
    if value is None and isinstance(headers, dict):
        for key, item in headers.items():
            if str(key).lower() == "authorization":
                value = item
                break
    if not isinstance(value, str):
        return None
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _tenant_tokens() -> Dict[str, str]:
    raw = (os.environ.get("TENANT_TOKENS") or "").strip()
    out: Dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        token, _, tenant = entry.partition(":")
        token, tenant = token.strip(), tenant.strip()
        if token and tenant:
            out[token] = tenant
    return out


def resolve_tenant(headers: Any) -> Principal:
    token = _header(headers)
    if not token:
        raise Unauthenticated("missing bearer token")
    platform_token = (os.environ.get("PLATFORM_TOKEN") or "").strip()
    if platform_token and hmac.compare_digest(token, platform_token):
        return Principal(tenant_id=DEFAULT_TENANT, principal_id="platform", token=token)
    tenant = None
    for configured, name in _tenant_tokens().items():
        if hmac.compare_digest(token, configured):
            tenant = name
            break
    if tenant:
        return Principal(tenant_id=tenant, principal_id=tenant, token=token)
    raise Unauthenticated("unknown bearer token")


def tenant_of(principal: Principal) -> str:
    if not principal or not principal.tenant_id:
        raise Unauthenticated("principal has no tenant")
    return principal.tenant_id
