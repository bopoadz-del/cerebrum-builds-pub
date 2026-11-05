"""Declared placeholder connectors for this product.

Every bound block here is a local Store block, so no connector is a declared
placeholder. The map exists for the factory probe, which skips a declared
placeholder's persistence round-trip and asserts its typed refusal instead.
"""

from __future__ import annotations

PLACEHOLDER_CONNECTORS = {}


def is_declared_refusal(capability_id, status_code, body) -> bool:
    if not PLACEHOLDER_CONNECTORS.get(capability_id):
        return False
    if status_code != 503 or not isinstance(body, dict):
        return False
    return str(body.get("error_kind") or "") == "unavailable"
