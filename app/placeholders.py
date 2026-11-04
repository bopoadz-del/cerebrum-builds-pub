"""Declared placeholder connectors.

This platform's capabilities all run against real, vendored blocks, so no
capability is declared a placeholder.  The module exists because the Factory's
probes read it: a product with a declared placeholder names it here, and the
probe then reports the typed refusal instead of judging it as a failure.
"""

from __future__ import annotations

from typing import Any, Dict

#: capability id -> the settings its connector still needs.
PLACEHOLDER_CONNECTORS: Dict[str, list] = {}


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    if not PLACEHOLDER_CONNECTORS.get(str(capability_id)):
        return False
    if int(status_code) not in (200, 503):
        return False
    return bool(isinstance(body, dict) and body.get("placeholder") is True)
