"""Auth and egress guards used at the edge of the platform.

Authentication itself is resolved from the bearer token by app.tenancy;
this module holds the primitives the routes and any outbound path share:
a constant-time token comparison, a private-address guard for a URL a
caller controls, and redaction for anything that reaches a log or an
error body.
"""

from __future__ import annotations

import hmac
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

BEARER_PREFIX = "bearer"

#: Hosts that must never be reached from a caller-supplied URL.
_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class SecurityError(ValueError):
    """A request refused before it reaches a handler."""


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    """The token in an ``Authorization: Bearer <token>`` header, or None."""
    scheme, _, token = str(authorization or "").partition(" ")
    token = token.strip()
    if scheme.strip().lower() != BEARER_PREFIX or not token:
        return None
    return token


def tokens_match(presented: str, known: str) -> bool:
    """Constant-time comparison: a token is never compared with ``==``."""
    if not presented or not known:
        return False
    return hmac.compare_digest(str(presented), str(known))


def redact(value: str, keep: int = 4) -> str:
    """A secret as it may appear in a log line: last ``keep`` characters only."""
    text = str(value or "")
    if len(text) <= keep:
        return "*" * len(text)
    return "*" * (len(text) - keep) + text[-keep:]


def _addresses(host: str):
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise SecurityError(f"host {host!r} does not resolve") from exc
    for info in infos:
        yield ipaddress.ip_address(info[4][0])


def assert_public_url(url: str, *, allowed_schemes: tuple = ("https",)) -> str:
    """Refuse a URL that would reach a private, loopback or metadata address.

    Every outbound call whose URL a caller can influence passes through
    here first. A literal IP is checked directly; a hostname is resolved
    and every resolved address is checked, so a DNS name pointing at
    127.0.0.1 or 169.254.169.254 is refused too.
    """
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in allowed_schemes:
        raise SecurityError(f"scheme {parsed.scheme or '(none)'!r} is not allowed")
    host = parsed.hostname or ""
    if not host:
        raise SecurityError("the URL has no host")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise SecurityError(f"host {host!r} is not reachable from this platform")
    for address in _addresses(host):
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise SecurityError(f"host {host!r} resolves to a non-public address")
    return url
