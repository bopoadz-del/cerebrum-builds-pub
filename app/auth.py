"""Fail-closed operator auth and CORS allowlist. No git-default secrets."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import HTTPException, Request
from starlette.middleware.cors import CORSMiddleware

OPERATOR_TOKEN_ENV = "OPERATOR_TOKEN"
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"
CORS_ALLOWLIST_ENV = "CORS_ALLOWLIST"

# Reject empty, short, and well-known placeholder values. Never fall back
# to a committed default — missing/unusable secrets deny the mutation.
_FORBIDDEN_SECRETS = frozenset(
    {
        "",
        "changeme",
        "change-me",
        "secret",
        "token",
        "password",
        "operator",
        "admin",
        "sample",
        "default",
        "test",
        "git-default",
        "placeholder",
        "x-api-token",
        "bearer",
        "authorization",
    }
)
_MIN_SECRET_LEN = 16


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str

    def as_dict(self) -> Dict[str, str]:
        return {"subject": self.subject, "role": self.role}


def _usable_secret(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    secret = raw.strip()
    if len(secret) < _MIN_SECRET_LEN:
        return None
    if secret.lower() in _FORBIDDEN_SECRETS:
        return None
    return secret


def configured_principals() -> Dict[str, Principal]:
    mapping: Dict[str, Principal] = {}
    operator = _usable_secret(os.environ.get(OPERATOR_TOKEN_ENV))
    if operator:
        mapping[operator] = Principal(subject="operator", role="operator")
    admin = _usable_secret(os.environ.get(ADMIN_TOKEN_ENV))
    if admin:
        mapping[admin] = Principal(subject="admin", role="admin")
    return mapping


def extract_presented_secret(request: Request) -> Optional[str]:
    authorization = request.headers.get("authorization") or ""
    scheme, _, remainder = authorization.partition(" ")
    if scheme.lower() == "bearer" and remainder.strip():
        return remainder.strip()
    header_token = request.headers.get("x-api-token")
    if header_token and header_token.strip():
        return header_token.strip()
    return None


def resolve_principal(request: Request) -> Principal:
    secrets = configured_principals()
    if not secrets:
        raise HTTPException(status_code=401, detail="operator secret not configured")
    presented = extract_presented_secret(request)
    if not presented:
        raise HTTPException(status_code=401, detail="token required")
    matched: Optional[Principal] = None
    for secret, principal in secrets.items():
        try:
            if hmac.compare_digest(presented, secret):
                matched = principal
                break
        except ValueError:
            continue
    if matched is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return matched


def require_operator(request: Request) -> Principal:
    """Operator (or admin) gate for mutating routes and RAG writes."""
    return resolve_principal(request)


def cors_allowlist() -> List[str]:
    raw = (os.environ.get(CORS_ALLOWLIST_ENV) or "").strip()
    if not raw:
        return []
    origins: List[str] = []
    for part in raw.split(","):
        origin = part.strip()
        if not origin or origin == "*":
            continue
        origins.append(origin)
    return origins


def install_cors(app) -> None:
    """Install CORS from the allowlist. Wildcard origins are refused."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowlist(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Token"],
    )
