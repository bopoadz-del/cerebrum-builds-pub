"""Edge guards for caller payloads.

A capability payload is a record, not a control message: a dispatch keyword
(``action``, ``operation``) or a store identifier (``id``) inside it is
refused rather than silently ignored. Nested ``__`` keys are refused as a
prototype-pollution shape.

Scope READS: the caller's mapping.
Scope WRITES: nothing.
Scope NEVER: no network.
"""

from __future__ import annotations

from typing import Any, Dict

RESERVED_KEYS = ("action", "operation", "id")


class PayloadRefused(ValueError):
    """The mapping is not a domain record."""


def _walk(value: Any, depth: int = 0) -> None:
    if depth > 6:
        raise PayloadRefused("payload nested too deeply")
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key)
            if name.startswith("__"):
                raise PayloadRefused("reserved key: " + name)
            _walk(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _walk(item, depth + 1)


def guard_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise PayloadRefused("payload must be an object")
    for key in RESERVED_KEYS:
        if key in payload:
            raise PayloadRefused(
                "reserved key %r in the payload; dispatch keys travel as "
                "call arguments, never as record fields" % key
            )
    _walk(payload)
