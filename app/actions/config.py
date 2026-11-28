"""Configuration capability.

The vendored config block owns the platform's block configuration.  A caller
that supplies a key and a value performs a real `set` and reads the effective
configuration back; a caller that supplies only a block name performs a `get`.
The answer reports what actually changed and a digest of the effective
configuration, not the request echoed back.

SCALE: one configuration read or write per call.
READS: caller fields; the block's in-process configuration.
WRITES: the block's configuration for this call, reported in the response.
NEVER: a claimed write the block did not apply.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute, execute_sequence

CAPABILITY_ID = "config"
ENTITY = "config"
BLOCK_IDS = ["config"]
BLOCK_DEFAULT_ACTIONS = {"config": "get"}
AUTHORED_BY = "codewhale exec"


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    block_name = str(data.get("config_block") or "platform").strip() or "platform"
    key = str(data.get("key") or "").strip()
    value = data.get("value")
    has_value = key and value is not None and str(value) != ""

    current = execute("config", {"block": block_name}, action="get")
    if block_failed(current):
        return fail(refusal_text(current))

    steps: List[Dict[str, Any]] = []
    if has_value:
        steps.append({"action": "set",
                      "input": {"block": block_name, "key": key, "value": value}})
    steps.append({"action": "get_all", "input": {}})

    resolved = execute_sequence("config", steps)
    if block_failed(resolved):
        return fail(refusal_text(resolved))

    configuration = {
        name: block
        for name, block in (resolved or {}).items()
        if isinstance(block, dict) and name not in {"block", "status"}
    }
    block_config = configuration.get(block_name) or {}
    return ok({
        "config_block": block_name,
        "key": key or None,
        "value": value if has_value else None,
        "operation": "set" if has_value else "get",
        "known_block": block_name in configuration,
        "applied": bool(has_value and key in block_config),
        "entries": len(configuration),
        "block_entries": len(block_config),
        "value_type": type(value).__name__ if has_value else None,
        "configuration": configuration,
        "config_digest": domain_rules.canonical_digest(configuration),
    })
