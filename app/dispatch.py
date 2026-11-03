"""Block dispatch: load the locked vendored block, call it once.

Each locked block lives at exactly one path (blocks.lock.json). A missing
file is an error, never a fallback: the platform does not carry a second
copy or a re-implementation of a Store block.

action is a KEYWORD, never a payload key. Handlers pass
action=BLOCK_DEFAULT_ACTIONS.get(block_id).
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

_ROOT = Path(__file__).resolve().parents[1]
_BLOCKS = _ROOT / "vendor" / "blocks"

LOCKED_BLOCKS: Dict[str, str] = {
    "analytics": "vendor/blocks/analytics/block.py",
    "approval_rules": "vendor/blocks/approval_rules/block.py",
    "audit": "vendor/blocks/audit/block.py",
    "audit_chain": "vendor/blocks/audit_chain/block.py",
    "construction_advisor": "vendor/blocks/construction_advisor/block.py",
    "cpm_engine": "vendor/blocks/cpm_engine/block.py",
    "dashboard": "vendor/blocks/dashboard/block.py",
    "document_engine": "vendor/blocks/document_engine/block.py",
    "estate_maintenance": "vendor/blocks/estate_maintenance/block.py",
    "evidence_chain": "vendor/blocks/evidence_chain/block.py",
    "evidence_classifier": "vendor/blocks/evidence_classifier/block.py",
    "evidence_or_refuse": "vendor/blocks/evidence_or_refuse/block.py",
    "evidence_verifier": "vendor/blocks/evidence_verifier/block.py",
    "finance_reconciliation": "vendor/blocks/finance_reconciliation/block.py",
    "finance_reconciliation_workflow": "vendor/blocks/finance_reconciliation_workflow/block.py",
    "formula_executor": "vendor/blocks/formula_executor/block.py",
    "governance_gate": "vendor/blocks/governance_gate/block.py",
    "ingestion_provenance": "vendor/blocks/ingestion_provenance/block.py",
    "notification": "vendor/blocks/notification/block.py",
    "search": "vendor/blocks/search/block.py",
    "storage": "vendor/blocks/storage/block.py",
    "validation": "vendor/blocks/validation/block.py",
    "version_diff": "vendor/blocks/version_diff/block.py",
    "workflow": "vendor/blocks/workflow/block.py",
}

#: What each block reads from its input (harvested contract). Not authority;
#: it is what the dispatch tells a caller building an envelope.
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "workflow": {"input_keys_read_by_block": ["steps", "pipeline_id", "trigger", "timeout"]},
    "event_bus": {"input_keys_read_by_block": ["topic", "payload", "message", "channel", "tool"]},
}

_LOADED: Dict[str, Any] = {}
_LOCK = threading.Lock()


class BlockUnavailable(RuntimeError):
    """The locked block could not be loaded from its declared path."""


class BlockRefused(RuntimeError):
    """The block ran and answered with a refusal."""


def load_block(block_id: str):
    block_id = str(block_id)
    with _LOCK:
        if block_id in _LOADED:
            return _LOADED[block_id]
        path = _ROOT / LOCKED_BLOCKS.get(block_id, f"vendor/blocks/{block_id}/block.py")
        if not path.is_file():
            raise BlockUnavailable(f"locked block {block_id!r} is absent from {path}")
        name = "platform_block_" + block_id.replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise BlockUnavailable(f"locked block {block_id!r} has no loader at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "run"):
            raise BlockUnavailable(f"locked block {block_id!r} declares no run()")
        _LOADED[block_id] = module
        return module


def execute(block_id: str, payload: Optional[Dict[str, Any]] = None,
            action: Optional[str] = None, params: Optional[Dict[str, Any]] = None,
            **extra: Any) -> Dict[str, Any]:
    module = load_block(block_id)
    kwargs: Dict[str, Any] = {"input": payload if isinstance(payload, dict) else {}}
    if action is not None:
        kwargs["action"] = action
    if isinstance(params, dict):
        kwargs.update(params)
    kwargs.update(extra)
    answer = module.run(**kwargs)
    if isinstance(answer, dict):
        return answer
    return {"status": "success", "result": answer}


def refused(answer: Any) -> Optional[str]:
    """The refusal reason in a block answer, or None for a success."""
    if not isinstance(answer, dict):
        return None
    status = str(answer.get("status") or "").lower()
    inner = answer.get("result") if isinstance(answer.get("result"), dict) else {}
    if status in {"error", "refused", "failed"}:
        return str(answer.get("error") or inner.get("error") or status)
    inner_status = str(inner.get("status") or "").lower()
    if inner_status in {"error", "refused", "failed"}:
        return str(inner.get("error") or inner_status)
    return None
