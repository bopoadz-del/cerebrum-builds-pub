"""Tenancy for this platform: one tenant per request, always.

The tenant is resolved from the authenticated principal -- the bearer token
the caller presented -- and never from a client-supplied name. Tokens come
from the deploy environment only: PLATFORM_TOKEN for the platform tenant and
TENANT_TOKENS (token:tenant pairs) for further tenants. No literal fallback.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

DEFAULT_TENANT = "local"

#: The value .env.example ships. It is never a credential: a deploy that
#: copies the example must not open a world-known tenant.
DEPLOY_TIME_PLACEHOLDER = "set-at-deploy"


class TenantRefused(PermissionError):
    """No token, an unbound token, or a client-named tenant."""


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str
    roles: Tuple[str, ...] = ("admin",)

    def to_dict(self) -> Dict[str, object]:
        return {"tenant_id": self.tenant_id, "name": self.name, "roles": list(self.roles)}


def _pairs(raw: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for chunk in str(raw or "").split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        left, right = chunk.split(":", 1)
        left, right = left.strip(), right.strip()
        if left and right:
            out.append((left, right))
    return out


def token_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    platform = (os.environ.get("PLATFORM_TOKEN") or "").strip()
    if platform == DEPLOY_TIME_PLACEHOLDER:
        platform = ""
    if platform:
        out[platform] = DEFAULT_TENANT
    for token, tenant in _pairs(os.environ.get("TENANT_TOKENS", "")):
        if token == DEPLOY_TIME_PLACEHOLDER:
            continue
        out[token] = tenant
    return out


def name_map() -> Dict[str, str]:
    return dict(_pairs(os.environ.get("TENANT_NAMES", "")))


def _token_tenant(token: str) -> str | None:
    """The tenant bound to a presented token, compared in constant time.

    A dict lookup compares the token byte by byte and stops at the first
    difference, so the time it takes is a function of how much of a guessed
    token is right. The scan below compares every candidate with a
    constant-time digest and records the match without an early return, and
    an unknown token costs the same as a known one. Bytes are compared, not
    str, because compare_digest refuses non-ASCII text.
    """
    import hmac

    presented = str(token).encode("utf-8", "surrogatepass")
    matched: str | None = None
    for candidate, tenant_id in token_map().items():
        if hmac.compare_digest(presented, str(candidate).encode("utf-8", "surrogatepass")):
            matched = tenant_id
    return matched


def resolve_tenant(headers: Mapping[str, str]) -> Tenant:
    header = str(headers.get("authorization") or headers.get("Authorization") or "")
    token = str(headers.get("x-platform-token") or "").strip()
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token:
        raise TenantRefused("no token presented")
    tenant_id = _token_tenant(token)
    if not tenant_id:
        raise TenantRefused("token is not bound to a tenant")
    return Tenant(tenant_id=tenant_id, name=name_map().get(tenant_id, tenant_id))


_CURRENT_TENANT: ContextVar[str | None] = ContextVar("platform_tenant", default=None)


def bind_tenant(tenant_id: str):
    return _CURRENT_TENANT.set(str(tenant_id))


def release_tenant(token) -> None:
    _CURRENT_TENANT.reset(token)


def current_tenant_id() -> str | None:
    value = _CURRENT_TENANT.get()
    return str(value) if value else None
