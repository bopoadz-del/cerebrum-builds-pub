"""Edge security helpers: authentication, redaction, private-address guard."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any, Mapping
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from app.tenancy import Principal, Unauthenticated, resolve_tenant

SENSITIVE_KEYS = ("authorization", "token", "password", "secret", "api_key", "apikey")


def require_principal(request: Request) -> Principal:
    try:
        return resolve_tenant(request.headers)
    except Unauthenticated as exc:
        raise HTTPException(status_code=401, detail={"error": str(exc), "error_kind": "unauthenticated"}) from None


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if any(part in str(key).lower() for part in SENSITIVE_KEYS) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def private_address_guard(url: str) -> str:
    """Refuse egress to a loopback/private/link-local destination.

    Returns the URL when it is public; raises ValueError otherwise. Hostnames
    are resolved and every returned address is checked, so a CNAME to a
    private range cannot slip through.
    """
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http(s) egress is allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("a URL with a host is required")
    candidates = []
    try:
        candidates.append(ipaddress.ip_address(host))
    except ValueError:
        try:
            for info in socket.getaddrinfo(host, None):
                candidates.append(ipaddress.ip_address(info[4][0]))
        except (OSError, ValueError):
            raise ValueError("cannot resolve egress host") from None
    for address in candidates:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("egress to a private address is refused")
    return str(url)


def auth_label(headers: Mapping[str, str] | Any) -> str:
    scheme = "bearer" if "authorization" in {str(k).lower() for k in dict(headers or {})} else "anonymous"
    return scheme
