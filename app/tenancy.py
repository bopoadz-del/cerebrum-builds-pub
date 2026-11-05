"""Tenancy: one tenant per request, resolved from the authenticated principal.

The tenant is never read from the payload. Tokens come from the deploy
environment only -- PLATFORM_TOKEN for the platform tenant and
TENANT_TOKENS (token:tenant pairs) for any further tenant -- and there is no
default value: a platform with no token configured refuses every request
rather than opening a well-known one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from app import config


class Unauthenticated(Exception):
    """The request carries no principal this platform knows."""


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    principal: str
    platform: bool = False


def _tenant_tokens() -> Dict[str, str]:
    raw = (os.environ.get("TENANT_TOKENS") or "").strip()
    out: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        token, _, tenant = pair.partition(":")
        token = token.strip()
        tenant = tenant.strip()
        if token and tenant:
            out[token] = tenant
    return out


def _bearer(auth: Any) -> Optional[str]:
    if auth is None:
        return None
    if isinstance(auth, str):
        value = auth.strip()
        if value.lower().startswith("bearer "):
            return value[7:].strip()
        return value or None
    if isinstance(auth, Mapping):
        for key, value in auth.items():
            if str(key).lower() in {"authorization", "auth", "token", "bearer"}:
                return _bearer(value)
        return None
    header = getattr(auth, "headers", None)
    if header is not None:
        return _bearer(dict(header))
    return None


def resolve_tenant(auth: Any) -> Tenant:
    """Resolve the caller's tenant, or refuse. Never invents a tenant."""
    token = _bearer(auth)
    if not token:
        raise Unauthenticated("missing bearer token")
    platform_token = (os.environ.get("PLATFORM_TOKEN") or "").strip()
    if platform_token and token == platform_token:
        return Tenant(tenant_id=config.PLATFORM_TENANT, principal="platform", platform=True)
    tenant_id = _tenant_tokens().get(token)
    if tenant_id:
        return Tenant(tenant_id=tenant_id, principal=tenant_id, platform=False)
    raise Unauthenticated("unknown bearer token")


def tenant_from_headers(headers: Mapping[str, str]) -> Tenant:
    return resolve_tenant(headers)
