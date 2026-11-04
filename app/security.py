"""Edge security: authentication dependency and outbound-address guard."""

from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from app.tenancy import Principal, Unauthenticated, resolve_tenant


def require_principal(request: Request) -> Principal:
    try:
        return resolve_tenant(request.headers)
    except Unauthenticated as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def is_private_address(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def guard_outbound_url(url: str) -> str:
    """Refuse egress to a private or loopback address (SSRF guard)."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("only http(s) URLs with a host are allowed")
    if is_private_address(parsed.hostname):
        raise ValueError("outbound URL resolves to a private address")
    return url


def rejection_body(field: str, reason: str, detail: str, allowed: Any = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ok": False,
        "error": detail,
        "rejected_field": field,
        "rejection_reason": reason,
    }
    if allowed:
        body["allowed_values"] = list(allowed)
    return body


def rejection_headers(field: str, reason: str, allowed: Any = None) -> Dict[str, str]:
    headers = {
        "X-Rejected-Field": json.dumps(field),
        "X-Rejection-Reason": str(reason),
    }
    if allowed:
        headers["X-Allowed-Values"] = json.dumps(list(allowed))
    return headers
