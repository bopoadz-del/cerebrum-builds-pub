"""Edge validation shared by the HTTP routes."""

from __future__ import annotations

from typing import Any, Dict, List

RESERVED_FIELDS = ("action", "id")
MAX_BODY_BYTES = 2_000_000


def reserved_fields(payload: Dict[str, Any]) -> List[str]:
    return [name for name in RESERVED_FIELDS if name in payload]


def body_too_large(raw: bytes) -> bool:
    return len(raw or b"") > MAX_BODY_BYTES
