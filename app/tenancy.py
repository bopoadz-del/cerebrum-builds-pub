"""Tenant resolution from the authenticated principal.

One tenant per request, always. The tenant comes from the bearer token the
deploy environment bound (``PLATFORM_TOKEN`` for the platform tenant,
``TENANT_TOKENS`` for further tenants) and never from the payload, a header the
caller chose, or a default that silently widens access.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Union

from app import config

DEFAULT_TENANT = config.DEFAULT_TENANT


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    source: str = "platform"

    def as_dict(self) -> Dict[str, str]:
        return {"tenant_id": self.tenant_id, "source": self.source}


def token_registry() -> Dict[str, str]:
    """token -> tenant_id, platform token first."""
    registry: Dict[str, str] = {}
    platform = config.platform_token()
    if platform:
        registry[platform] = DEFAULT_TENANT
    for token, tenant in config.tenant_tokens().items():
        registry.setdefault(token, tenant)
    return registry


def bearer_token(auth: Union[None, str, Mapping[str, str]]) -> Optional[str]:
    """Extract the token from a header mapping or a bare ``Bearer`` value."""
    if not auth:
        return None
    if isinstance(auth, str):
        value = auth.strip()
    else:
        lowered = {str(k).lower(): v for k, v in dict(auth).items()}
        value = str(lowered.get("authorization") or "").strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value or None


def authenticate(auth: Union[None, str, Mapping[str, str]]) -> Optional[Principal]:
    """The principal this request acts as, or None (which the route answers 401)."""
    token = bearer_token(auth)
    if not token:
        return None
    for known, tenant in token_registry().items():
        if hmac.compare_digest(str(known), str(token)):
            source = "platform" if tenant == DEFAULT_TENANT else "tenant"
            return Principal(tenant_id=tenant, source=source)
    return None


def resolve_tenant(auth: Union[None, str, Mapping[str, str]]) -> Optional[Principal]:
    """Backwards-compatible name used by the kernel's S12 probe."""
    return authenticate(auth)
