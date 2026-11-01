"""Payload guards: no client-supplied tenancy or control keys."""

from __future__ import annotations

from typing import Any, Mapping

RESERVED_PAYLOAD_KEYS = frozenset(
    {
        "action",
        "tenant",
        "tenant_id",
        "tenant_name",
        "org_id",
        "organisation_id",
        "entity",
        "block_id",
    }
)


class PayloadRefused(ValueError):
    """A payload carried a key the platform owns."""


def guard_payload(payload: Mapping[str, Any] | None) -> None:
    if not isinstance(payload, Mapping):
        raise PayloadRefused("payload must be an object")
    bad = sorted(str(k) for k in payload if str(k) in RESERVED_PAYLOAD_KEYS)
    if bad:
        raise PayloadRefused("reserved field(s): " + ", ".join(bad))


def sanitise_error(message: Any, limit: int = 300) -> str:
    """An error body must never carry a token or a connection string."""
    import re

    text = re.sub(
        r"(?i)(bearer|token|api[_-]?key|password|secret)\s*[:=]\s*\S+",
        r"\1=***",
        str(message or ""),
    )
    text = re.sub(r"(?i)([a-z]+://)[^@\s/]+@", r"\1***@", text)
    return text[:limit]
