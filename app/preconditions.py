"""Platform preconditions. Never raises: boot reports, it does not die.

A block that mints an id it later needs (team is the one this platform
uses) can ask here for the platform's stable id for that resource, so the
id is carried across calls instead of being re-invented per request.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict

_RESOURCES: Dict[str, str] = {}


def resource_id(kind: str) -> str:
    """The platform's id for one resource kind, minted once per process."""
    key = str(kind or "").strip().lower()
    if not key:
        return ""
    if key not in _RESOURCES:
        _RESOURCES[key] = "%s_%s" % (key, hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16])
    return _RESOURCES[key]


def ensure_all() -> Dict[str, Any]:
    return {"ok": True, "preconditions": [], "resources": dict(_RESOURCES)}
