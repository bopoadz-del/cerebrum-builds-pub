"""Tenant resolution from the authenticated principal.

The tenant is never taken from a request payload or a client-supplied
header. ``PLATFORM_TOKEN`` names the platform tenant; ``TENANT_TOKENS``
is a comma-separated ``token:tenant`` list for further tenants.
"""

from __future__ import annotations

import hmac
import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, Optional

PLATFORM_TENANT = "platform"
_current_tenant: ContextVar[str] = ContextVar("current_tenant", default=PLATFORM_TENANT)


class Unauthorized(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    token: str


def _presented(headers) -> str:
    if isinstance(headers, str):
        value = headers
    elif hasattr(headers, "get"):
        value = headers.get("authorization") or headers.get("Authorization") or ""
    else:
        value = ""
    value = str(value or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _tenant_tokens() -> Dict[str, str]:
    raw = (os.getenv("TENANT_TOKENS") or "").strip()
    out: Dict[str, str] = {}
    for item in raw.split(","):
        pair = item.strip()
        if not pair or ":" not in pair:
            continue
        token, tenant = pair.split(":", 1)
        token, tenant = token.strip(), tenant.strip()
        if token and tenant:
            out[token] = tenant
    return out


def resolve_tenant(headers) -> Principal:
    token = _presented(headers)
    if not token:
        raise Unauthorized("missing bearer token")
    platform_token = (os.getenv("PLATFORM_TOKEN") or "").strip()
    if platform_token and hmac.compare_digest(token, platform_token):
        return Principal(user_id=PLATFORM_TENANT, tenant_id=PLATFORM_TENANT, token=token)
    for candidate, tenant in _tenant_tokens().items():
        if hmac.compare_digest(token, candidate):
            return Principal(user_id=tenant, tenant_id=tenant, token=token)
    raise Unauthorized("unknown bearer token")


def set_current_tenant(tenant_id: str):
    return _current_tenant.set(str(tenant_id or PLATFORM_TENANT))


def reset_current_tenant(value) -> None:
    _current_tenant.reset(value)


def current_tenant() -> str:
    return _current_tenant.get()


def require_principal(request) -> Principal:
    return resolve_tenant(getattr(request, "headers", {}))
