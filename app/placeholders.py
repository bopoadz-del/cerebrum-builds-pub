"""Declared placeholder connectors for this platform.

This build declares none: every connector the capabilities use is either a
local vendored block or a documented setting the operator supplies at deploy
time.  The module keeps the factory's shape so a capability can ask for a
typed refusal without importing an absent module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

UNAVAILABLE_KIND = "unavailable"
UNAVAILABLE_STATUS = 503

PLACEHOLDER_CONNECTORS: Dict[str, List[str]] = {}


def setting_for(connector_id: str) -> str:
    return connector_id.upper() + "_CREDENTIALS"


def refusal_for(capability_id: str) -> Optional[Dict[str, Any]]:
    connectors = PLACEHOLDER_CONNECTORS.get(capability_id) or []
    if not connectors:
        return None
    return {
        "ok": False,
        "capability": capability_id,
        "error_kind": UNAVAILABLE_KIND,
        "error": "connector not configured",
        "settings": [setting_for(c) for c in connectors],
    }


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    return (
        status_code == UNAVAILABLE_STATUS
        and isinstance(body, dict)
        and body.get("error_kind") == UNAVAILABLE_KIND
    )
