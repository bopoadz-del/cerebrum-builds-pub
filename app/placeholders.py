"""Declared placeholder connectors for this build.

None: every capability in this platform runs on in-process blocks. The
mapping is declared (rather than left absent) so the acceptance harness reads
an explicit "no placeholders" answer instead of guessing from an ImportError.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

#: capability_id -> the settings its placeholder connector would need.
PLACEHOLDER_CONNECTORS: Dict[str, list] = {}


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    """A capability whose connector is a declared placeholder answers 503 with
    error_kind "unavailable"; nothing else is a declared refusal."""
    if capability_id not in PLACEHOLDER_CONNECTORS:
        return False
    if int(status_code) != 503 or not isinstance(body, Mapping):
        return False
    return str(body.get("error_kind") or "") == "unavailable"
