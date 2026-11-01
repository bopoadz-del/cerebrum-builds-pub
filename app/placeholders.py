"""Capabilities whose connectors are declared placeholders.

This blueprint declares none: every capability in this platform runs end to
end against the vendored blocks. The module and its helpers stay because the
HTTP surface and the console ask every capability whether a connector is
missing before running it; an empty map is the truthful answer here and a
future connector is declared in exactly one place.

A capability listed in ``PLACEHOLDER_CONNECTORS`` would answer HTTP 503,
``ok: false``, ``error_kind: "unavailable"``, naming the environment setting
the operator must supply, before validation and before its handler runs, so
nothing is stored and no caller mistakes a placeholder for an integration.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

UNAVAILABLE_KIND = "unavailable"
REFUSAL_LOG_ENV = "PLACEHOLDER_REFUSAL_LOG"
UNAVAILABLE_STATUS = 503
SETTING_SUFFIX = "_CREDENTIALS"

#: capability id -> the connectors the blueprint declares as placeholders.
PLACEHOLDER_CONNECTORS: Dict[str, List[str]] = {}


def setting_for(connector_id: str) -> str:
    return connector_id.upper() + SETTING_SUFFIX


def _record(capability_id: str) -> None:
    path = os.environ.get(REFUSAL_LOG_ENV)
    if not path:
        return
    running = os.environ.get("PYTEST_CURRENT_TEST") or ""
    test = running.rsplit(" (", 1)[0]
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"test": test, "capability": capability_id}) + "\n")
    except OSError:
        pass


def refusal_for(capability_id: str) -> Optional[Dict[str, Any]]:
    """The typed refusal for a declared capability, else None."""
    connectors = PLACEHOLDER_CONNECTORS.get(capability_id) or []
    if not connectors:
        return None
    _record(capability_id)
    settings = [setting_for(c) for c in connectors]
    return {
        "ok": False,
        "error_kind": UNAVAILABLE_KIND,
        "capability": capability_id,
        "connectors": list(connectors),
        "settings": settings,
        "error": "not configured: " + ", ".join(
            "%s is a placeholder connector (needs %s)" % (c, s)
            for c, s in zip(connectors, settings)
        ),
    }


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    connectors = PLACEHOLDER_CONNECTORS.get(capability_id) or []
    return (
        bool(connectors)
        and status_code == UNAVAILABLE_STATUS
        and isinstance(body, dict)
        and body.get("ok") is False
        and body.get("error_kind") == UNAVAILABLE_KIND
        and list(body.get("settings") or []) == [setting_for(c) for c in connectors]
    )
