"""Tenant resolution from the authenticated principal, never from a payload.

One tenant per request. ``PLATFORM_TOKEN`` names the platform tenant;
``TENANT_TOKENS`` carries further ``token:tenant`` pairs. With no token in
the environment the platform refuses every request -- it never falls back to
a baked value.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

WRITE_PERMISSION = "product.write"
READ_PERMISSION = "product.read"
PROCESS_PERMISSION = "product.process"

PLATFORM_TENANT = "local"


class AuthenticationError(RuntimeError):
    """No principal could be resolved from the request."""


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    principal: str
    permissions: Tuple[str, ...] = field(
        default_factory=lambda: (WRITE_PERMISSION, READ_PERMISSION, PROCESS_PERMISSION)
    )


def _token_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    platform = (os.getenv("PLATFORM_TOKEN") or "").strip()
    if platform:
        mapping[platform] = (os.getenv("PLATFORM_TENANT") or PLATFORM_TENANT).strip()
    for pair in (os.getenv("TENANT_TOKENS") or "").split(","):
        token, _, tenant = pair.partition(":")
        token = token.strip()
        tenant = tenant.strip()
        if token and tenant and token not in mapping:
            mapping[token] = tenant
    return mapping


def bearer_token(headers: Optional[Dict[str, str]]) -> str:
    raw = ""
    for key, value in (headers or {}).items():
        if str(key).lower() == "authorization":
            raw = str(value)
            break
    if not raw:
        raise AuthenticationError("missing Authorization header")
    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Authorization must be a Bearer token")
    return token.strip()


def resolve_tenant(headers: Optional[Dict[str, str]]) -> Tenant:
    token = bearer_token(headers)
    tenant_id = ""
    for candidate, mapped in _token_map().items():
        if hmac.compare_digest(candidate, token):
            tenant_id = mapped
            break
    if not tenant_id:
        raise AuthenticationError("token is not a configured principal")
    principal = "principal-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return Tenant(tenant_id=tenant_id, principal=principal)


def tenant_headers(headers: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    tenant = resolve_tenant(headers)
    return tenant.tenant_id, tenant.principal


def approved_principals() -> List[str]:
    raw = os.getenv("APPROVED_PRINCIPALS") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def is_approved_principal(name: str) -> bool:
    return str(name or "").strip() in set(approved_principals())
