"""Declared placeholder connectors for this product.

No capability of this platform is built on a connector that is a declared
placeholder: every bound Store block is vendored and executes in-process.
The empty declaration is what lets the gates judge every capability.
"""

from __future__ import annotations

from typing import Any, Dict

PLACEHOLDER_CONNECTORS: Dict[str, Any] = {}


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    return bool(PLACEHOLDER_CONNECTORS.get(capability_id))
