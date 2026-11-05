"""Block dispatch: load a vendored block from its locked path and run it.

Blocks are action-dispatched: the operation travels as the ``action=``
keyword, never inside the caller's payload dict. A block is loaded from the
path ``blocks.lock.json`` pins it to and from nowhere else. A locked block
absent from its path is an error -- never a fallback, never a
reimplementation.

Some blocks read the operation from inside the record they are given (their
own contract, declared in their source); dispatch adapts the keyword to that
shape for the blocks that declare it. The caller still passes ``action=``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "blocks.lock.json"
VENDOR_ROOT = ROOT / "vendor" / "blocks"

#: The top-level input keys each bound block reads. Used by the factory probe
#: to tell a "payload one level too deep" refusal from a genuine one.
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "validation": {"input_keys_read_by_block": ["block", "code", "name", "path", "metadata"]},
    "config": {"input_keys_read_by_block": ["block", "key", "value"]},
    "version": {"input_keys_read_by_block": ["name", "version", "block", "dependency", "component"]},
    "auth": {"input_keys_read_by_block": ["api_key", "name", "role", "owner", "block"]},
    "notification": {
        "input_keys_read_by_block": ["message", "channel", "channels", "to", "subject", "block", "tool", "payload"]
    },
    "email": {"input_keys_read_by_block": ["to", "subject", "body", "template", "variables"]},
    "database": {"input_keys_read_by_block": ["sql", "table", "columns", "values", "where", "limit"]},
    "orchestrator": {"input_keys_read_by_block": ["steps", "initial_input", "max_steps"]},
    "knowledge": {"input_keys_read_by_block": ["question", "query", "text", "documents"]},
    "memory": {"input_keys_read_by_block": ["key", "value", "ttl", "namespace"]},
    "audit": {
        "input_keys_read_by_block": [
            "principal_id", "user_id", "action_name", "event", "resource_type",
            "resource_id", "status", "details", "category", "tenant_id",
        ]
    },
    "governance_gate": {
        "input_keys_read_by_block": ["tenant_id", "action_type", "target_id", "requester_id", "approver_id"]
    },
    "formula_executor": {
        "input_keys_read_by_block": ["custom_code", "input_values", "formula_key", "operation", "formula_description"]
    },
    "evidence_chain": {
        "input_keys_read_by_block": ["tenant_id", "action_type", "principal_id", "payload", "result"]
    },
    "ingestion_provenance": {
        "input_keys_read_by_block": [
            "product_id", "blueprint_id", "factory_commit", "blocks_commit", "plan",
            "inputs_hash", "root", "source", "page", "sheet", "action",
        ]
    },
    "analytics": {"input_keys_read_by_block": ["metric", "value", "period", "tags", "window_size"]},
    "pdf": {"input_keys_read_by_block": ["file_path", "pdf_path", "text", "url"]},
    "dashboard": {"input_keys_read_by_block": ["widgets", "layout", "metrics", "refresh_interval"]},
    "workflow": {"input_keys_read_by_block": ["steps", "pipeline_id", "trigger", "timeout"]},
    "approval_rules": {
        "input_keys_read_by_block": ["project_id", "source_doc", "extracted", "rule_id", "reviewer", "action"]
    },
    "transaction_state_machine": {
        "input_keys_read_by_block": ["entity_id", "vertical", "event", "actor", "operation"]
    },
    "version_diff": {"input_keys_read_by_block": ["left", "right", "text_a", "text_b", "path", "action"]},
    "workbench": {"input_keys_read_by_block": ["brief", "mutable_paths", "prompt_template"]},
    "vector_search": {"input_keys_read_by_block": ["query", "text", "input", "documents"]},
}

#: Blocks whose own contract reads the operation from the input record rather
#: than a params action.
ACTION_IN_INPUT = frozenset(
    {
        "approval_rules",
        "evidence_chain",
        "ingestion_provenance",
        "governance_gate",
        "version_diff",
    }
)

#: Blocks whose operation parameter is named something other than ``action``.
ACTION_PARAM_NAME: Dict[str, str] = {"vector_search": "operation"}


class BlockUnavailable(RuntimeError):
    """A bound block could not be loaded from its locked path."""


def _lock_entry(block_id: str) -> Optional[str]:
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    blocks = data.get("blocks") or data
    entry = blocks.get(block_id) if isinstance(blocks, dict) else None
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("path", "file", "source", "module_path"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def locked_path(block_id: str) -> Path:
    """The one path this block may be loaded from."""
    declared = _lock_entry(block_id)
    path = (ROOT / declared).resolve() if declared else (VENDOR_ROOT / block_id).resolve()
    if path.is_dir():
        return (path / "block.py").resolve()
    return path


_LOADED: Dict[str, ModuleType] = {}


def load_block(block_id: str) -> ModuleType:
    key = str(block_id)
    cached = _LOADED.get(key)
    if cached is not None:
        return cached
    path = locked_path(key)
    if not path.is_file():
        raise BlockUnavailable(
            "locked block %r is absent from its declared path %s" % (key, path)
        )
    module_name = "vendor_blocks.%s" % key.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise BlockUnavailable("block %r at %s is not importable" % (key, path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    _LOADED[key] = module
    return module


def _entry_point(module: ModuleType):
    for name in ("execute", "run", "handle"):
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    raise BlockUnavailable(
        "block %r declares no execute()/run()/handle()" % getattr(module, "__name__", "?")
    )


def _is_argument_error(exc: TypeError) -> bool:
    text = str(exc)
    return any(word in text for word in ("argument", "parameter", "positional", "keyword"))


def _invoke(
    block_id: str,
    entry,
    payload: Dict[str, Any],
    action: Optional[str],
    params: Dict[str, Any],
):
    if action is not None:
        if block_id in ACTION_IN_INPUT:
            payload = dict(payload)
            payload["action"] = action
        params = dict(params)
        params[ACTION_PARAM_NAME.get(block_id, "action")] = action
    # The vendored adapters build the block's own params dict from keyword
    # arguments, so a block parameter travels as a keyword, not as a nested
    # "params" mapping (which the adapter would hand the block as one param
    # named "params").
    keywords = dict(params)
    attempts: List[Any] = []
    if keywords:
        attempts.append(lambda: entry(input=payload, **keywords))
        attempts.append(lambda: entry(payload, **keywords))
        attempts.append(lambda: entry(**{**payload, **keywords}))
    attempts.append(lambda: entry(input=payload))
    attempts.append(lambda: entry(payload))
    attempts.append(lambda: entry(**payload))
    attempts.append(lambda: entry())
    last: Optional[TypeError] = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            if not _is_argument_error(exc):
                raise
            last = exc
    raise last if last is not None else TypeError("no callable form matched")


def execute(
    block_id: str,
    payload: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run one block and return its answer as a dict.

    A refusal is data the capability must fail closed on -- it is returned,
    never swallowed. A loader failure is returned with ``error_kind
    "unavailable"`` so the caller can name the missing block honestly.
    """
    try:
        module = load_block(block_id)
        entry = _entry_point(module)
        call_payload: Dict[str, Any] = dict(payload or {})
        call_payload.update({k: v for k, v in kwargs.items() if k != "action"})
        answer = _invoke(block_id, entry, call_payload, action, dict(params or {}))
    except BlockUnavailable as exc:
        return {
            "ok": False,
            "status": "error",
            "error_kind": "unavailable",
            "block": block_id,
            "action": action,
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 -- a refusal is data, not a crash
        return {
            "ok": False,
            "status": "error",
            "block": block_id,
            "action": action,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }
    if answer is None:
        return {"ok": True, "block": block_id, "action": action, "result": {}}
    if isinstance(answer, dict):
        answer.setdefault("block", block_id)
        return answer
    if isinstance(answer, list):
        return {"ok": True, "block": block_id, "action": action, "items": answer}
    return {"ok": True, "block": block_id, "action": action, "value": answer}


def failed(answer: Any) -> bool:
    """True when a block answer is a refusal the capability must honour."""
    if not isinstance(answer, dict):
        return False
    if answer.get("ok") is False:
        return True
    status = str(answer.get("status", "")).lower()
    if status in {"error", "failed", "refused", "partial", "validation_error", "not_approved"}:
        return True
    return bool(answer.get("error")) and status not in {"success", "ok", "help"}
