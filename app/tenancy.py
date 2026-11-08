"""One tenant per request, always.

The tenant is resolved from the authenticated principal -- the bearer token
the caller presented -- never from a client-supplied name. Tokens come from
the deploy environment only: PLATFORM_TOKEN for the platform tenant and
TENANT_TOKENS (token:tenant pairs) for further tenants. No literal fallback.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

DEFAULT_TENANT = "local"


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
    if platform:
        out[platform] = DEFAULT_TENANT
    for token, tenant in _pairs(os.environ.get("TENANT_TOKENS", "")):
        out[token] = tenant
    return out


def name_map() -> Dict[str, str]:
    return dict(_pairs(os.environ.get("TENANT_NAMES", "")))


def resolve_tenant(headers: Mapping[str, str]) -> Tenant:
    header = str(headers.get("authorization") or headers.get("Authorization") or "")
    token = str(headers.get("x-platform-token") or "").strip()
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token:
        raise TenantRefused("no token presented")
    tenant_id = token_map().get(token)
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
