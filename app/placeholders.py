"""Declared placeholder connectors and the typed refusal they answer.

This platform has no third-party connector that remains unimplemented: every
capability persists to the platform's own database and reads the uploaded
contract/BOQ from the product tree. The module is kept because the Factory's
probe and the capability roster ask every product whether a capability needs
an operator-configured connector; the answer here is "none".
"""

from __future__ import annotations

from typing import Dict, List, Optional

#: capability -> the connectors it needs. Empty list (or absent) means the
#: capability is fully servable today.
PLACEHOLDER_CONNECTORS: Dict[str, List[str]] = {}

#: connector -> the settings an operator supplies to make it live.
CONNECTOR_SETTINGS: Dict[str, List[str]] = {}

#: Connectors this build actually implements.
IMPLEMENTED_CONNECTORS: frozenset = frozenset()

UNAVAILABLE = "unavailable"


def connectors_for(capability_id: str) -> List[str]:
    return list(PLACEHOLDER_CONNECTORS.get(str(capability_id or ""), []) or [])


def missing_connectors(capability_id: str) -> List[str]:
    return [name for name in connectors_for(capability_id) if name not in IMPLEMENTED_CONNECTORS]


def unavailable_settings(capability_id: str) -> List[str]:
    settings: List[str] = []
    for name in missing_connectors(capability_id):
        for setting in CONNECTOR_SETTINGS.get(name, []):
            if setting not in settings:
                settings.append(setting)
    return settings


def refusal(capability_id: str) -> Optional[Dict[str, object]]:
    """The 503 body, or None when the capability has every connector it needs."""
    missing = missing_connectors(capability_id)
    if not missing:
        return None
    return {
        "ok": False,
        "error_kind": UNAVAILABLE,
        "error": "connector unavailable: " + ", ".join(missing),
        "connectors": missing,
        "settings": unavailable_settings(capability_id),
        "capability_id": capability_id,
    }


def is_declared_refusal(capability_id: str, status_code: int, body: object) -> bool:
    if int(status_code) != 503 or not isinstance(body, dict):
        return False
    if body.get("error_kind") != UNAVAILABLE:
        return False
    expected = unavailable_settings(capability_id)
    return bool(expected) and list(body.get("settings") or []) == expected
