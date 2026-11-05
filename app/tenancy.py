"""Tenant resolution from the authenticated principal, never the payload.

Tokens are deploy-time settings: ``PLATFORM_TOKEN`` for the platform tenant
and ``TENANT_TOKENS`` (``token:tenant`` pairs, comma-separated) for further
tenants. There is no fallback token in code -- a missing setting fails
closed, it does not open a well-known tenant.

Roles are the program roles this platform knows: a Program Director runs the
programme, a Registrar enrols learners and administers tracks, Faculty chair
sessions, a Learner submits work and sits defenses, a Reviewer returns
capstone verdicts.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

DEFAULT_TENANT = "local"
PROGRAM_DIRECTOR = "Program Director"
PROGRAM_ROLES = (
    "Program Director",
    "Registrar",
    "Faculty",
    "Learner",
    "Reviewer",
)


class TenantError(RuntimeError):
    """Authentication or tenancy could not be resolved."""


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    token: str = ""
    authenticated: bool = True

    def has_role(self, *roles: str) -> bool:
        return any(role in self.roles for role in roles)

    def can_write(self) -> bool:
        return self.has_role(*PROGRAM_ROLES)


def _bearer(headers: Optional[Mapping[str, str]]) -> Optional[str]:
    if not headers:
        return None
    raw = headers.get("authorization") or headers.get("Authorization")
    if not raw:
        return None
    parts = str(raw).strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _tenant_tokens() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    raw = (os.getenv("TENANT_TOKENS") or "").strip()
    for entry in raw.split(","):
        if not entry.strip() or ":" not in entry:
            continue
        token, _, tenant = entry.partition(":")
        token, tenant = token.strip(), tenant.strip()
        if token and tenant:
            mapping[token] = tenant
    return mapping


def _tenant_roles() -> Dict[str, List[str]]:
    roles: Dict[str, List[str]] = {}
    raw = (os.getenv("TENANT_ROLES") or "").strip()
    for entry in raw.split(","):
        if ":" not in entry:
            continue
        tenant, _, names = entry.partition(":")
        roles[tenant.strip()] = [part.strip() for part in names.split("|") if part.strip()]
    return roles


def resolve_tenant(headers: Optional[Mapping[str, str]] = None) -> Principal:
    """Resolve the caller's tenant, or raise TenantError (401 upstream)."""
    token = _bearer(headers)
    if not token:
        raise TenantError("missing bearer token")
    platform_token = (os.getenv("PLATFORM_TOKEN") or "").strip()
    if platform_token and hmac.compare_digest(token, platform_token):
        return Principal(
            tenant_id=DEFAULT_TENANT,
            user_id="platform-director",
            roles=(PROGRAM_DIRECTOR,),
            token=token,
        )
    for candidate, tenant in _tenant_tokens().items():
        if hmac.compare_digest(token, candidate):
            roles = tuple(_tenant_roles().get(tenant) or ("Faculty",))
            return Principal(
                tenant_id=tenant,
                user_id=f"user@{tenant}",
                roles=roles,
                token=token,
            )
    raise TenantError("unknown bearer token")


def principal_from_payload(
    payload: Mapping[str, object], headers: Optional[Mapping[str, str]] = None
) -> Principal:
    """The tenant is always the authenticated principal's; a payload's
    tenant name is ignored on purpose."""
    return resolve_tenant(headers)


def require_role(principal: Principal, allowed: Iterable[str]) -> None:
    if not any(role in allowed for role in principal.roles):
        raise PermissionError(
            "role %s is not permitted; allowed: %s"
            % (", ".join(principal.roles) or "(none)", ", ".join(sorted(allowed)))
        )
