"""Tenant resolution from the authenticated principal, never the payload.

PLATFORM_TOKEN names the platform tenant; TENANT_TOKENS carries
``token:tenant`` pairs for further tenants.  No token is ever baked into
runtime code: absent deploy configuration means no principal.
"""

from __future__ import annotations

import hmac
import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Optional

PLATFORM_TENANT = "platform"

# The tenant of the request currently being served.  The route sets it from
# the authenticated principal; a handler may use it for READ-ONLY domain
# lookups (matching, availability, conflict checks).  Persistence stays in
# the route, which owns the tenant-scoped save().
_CURRENT_TENANT: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant_id: Optional[str]):
    return _CURRENT_TENANT.set(tenant_id)


def reset_current_tenant(token) -> None:
    _CURRENT_TENANT.reset(token)


def current_tenant() -> Optional[str]:
    return _CURRENT_TENANT.get()


class Unauthorized(Exception):
    """No valid principal on the request."""


@dataclass(frozen=True)
class Tenant:
    tenant_id: str


def _header_value(auth: Any) -> str:
    if auth is None:
        return ""
    if isinstance(auth, str):
        raw = auth
    elif isinstance(auth, dict):
        raw = auth.get("Authorization") or auth.get("authorization") or ""
        raw = str(raw)
    elif hasattr(auth, "get"):
        raw = auth.get("authorization") or auth.get("Authorization") or ""
        raw = str(raw)
    else:
        raw = str(getattr(auth, "headers", "") or "")
    raw = raw.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    return raw


def _tenant_tokens() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for pair in (os.getenv("TENANT_TOKENS") or "").split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        token, tenant = pair.split(":", 1)
        token, tenant = token.strip(), tenant.strip()
        if token and tenant:
            out[token] = tenant
    return out


def resolve_tenant(auth: Any) -> Tenant:
    token = _header_value(auth)
    if not token:
        raise Unauthorized("missing bearer token")
    platform_token = (os.getenv("PLATFORM_TOKEN") or "").strip()
    if platform_token and hmac.compare_digest(token, platform_token):
        return Tenant(PLATFORM_TENANT)
    for candidate, tenant in _tenant_tokens().items():
        if hmac.compare_digest(token, candidate):
            return Tenant(tenant)
    raise Unauthorized("unknown bearer token")


def optional_tenant(auth: Any) -> Optional[Tenant]:
    try:
        return resolve_tenant(auth)
    except Unauthorized:
        return None
