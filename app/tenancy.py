"""Tenant resolution from the authenticated principal.

The tenant is NEVER read from a request payload. A bearer token resolves to
exactly one tenant: PLATFORM_TOKEN -> the platform tenant, and each
``token:tenant`` pair in TENANT_TOKENS -> that tenant.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

DEFAULT_TENANT = "local"


class Unauthenticated(RuntimeError):
    """No bearer token, or one the deploy environment does not know."""


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    token: str
    roles: tuple = ("operator",)


def _header_value(headers: Any, name: str) -> Optional[str]:
    if headers is None:
        return None
    if isinstance(headers, str):
        return headers if name.lower() == "authorization" else None
    getter = getattr(headers, "get", None)
    if getter is not None:
        value = getter(name) or getter(name.title()) or getter(name.upper())
        if value:
            return str(value)
    try:
        for key, value in dict(headers).items():
            if str(key).lower() == name.lower():
                return str(value)
    except (TypeError, ValueError):
        return None
    return None


def bearer_token(headers: Any) -> Optional[str]:
    raw = _header_value(headers, "authorization")
    if not raw:
        return None
    scheme, _, token = str(raw).partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _platform_token() -> Optional[str]:
    value = (os.environ.get("PLATFORM_TOKEN") or "").strip()
    return value or None


def tenant_tokens() -> dict:
    pairs = {}
    for chunk in (os.environ.get("TENANT_TOKENS") or "").split(","):
        token, _, tenant = chunk.strip().partition(":")
        if token and tenant:
            pairs[token.strip()] = tenant.strip()
    return pairs


def resolve_tenant(headers: Any) -> Principal:
    token = bearer_token(headers)
    if not token:
        raise Unauthenticated("missing bearer token")
    platform = _platform_token()
    if platform and hmac.compare_digest(token, platform):
        return Principal(tenant_id=DEFAULT_TENANT, user_id="operator", token=token)
    for known, tenant in tenant_tokens().items():
        if hmac.compare_digest(token, known):
            return Principal(tenant_id=tenant, user_id="operator@" + tenant, token=token)
    raise Unauthenticated("unknown bearer token")


def principal_to_dict(principal: Principal) -> dict:
    return {"tenant_id": principal.tenant_id, "user_id": principal.user_id, "roles": list(principal.roles)}
