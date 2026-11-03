"""Tenant resolution from the authenticated principal.

Tokens come from the deploy environment only: PLATFORM_TOKEN for the
platform tenant, TENANT_TOKENS ("token:tenant,...") for further tenants.
There is no baked token and no fallback: with none configured, every
request is unauthenticated and every /v1 route answers 401.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Mapping, Optional

PLATFORM_TENANT = "local"


class TenantError(Exception):
    """No valid principal on the request."""


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    principal_id: str
    token_fingerprint: str


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    for key, value in (headers or {}).items():
        if str(key).lower() == name:
            return str(value)
    return None


def _token_tenants() -> dict:
    pairs = {}
    platform = (os.getenv("PLATFORM_TOKEN") or "").strip()
    if platform:
        pairs[platform] = PLATFORM_TENANT
    raw = os.getenv("TENANT_TOKENS") or ""
    for item in raw.split(","):
        token, _, tenant = item.partition(":")
        token = token.strip()
        tenant = tenant.strip()
        if token and tenant:
            pairs[token] = tenant
    return pairs


def resolve_tenant(headers: Mapping[str, str]) -> Principal:
    raw = _header(headers, "authorization") or ""
    scheme, _, token = raw.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise TenantError("missing bearer token")
    for known, tenant in _token_tenants().items():
        if hmac.compare_digest(token, known):
            return Principal(tenant_id=tenant, principal_id="principal-" + tenant,
                             token_fingerprint=known[-4:])
    raise TenantError("unknown bearer token")


def approved_principals() -> set:
    raw = os.getenv("APPROVED_PRINCIPALS") or ""
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_approved_principal(value: str) -> bool:
    return str(value or "").strip() in approved_principals()
