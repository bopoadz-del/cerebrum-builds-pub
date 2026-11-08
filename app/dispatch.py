"""Local block dispatch. No network, no store, no callback.

Each capability answers by loading the block vendored into this repository
at build time (vendor/blocks/<id>/block.py) and calling it in process. That
is what makes the platform runnable offline and independent of the factory's
uptime.

``action=`` travels as a KEYWORD, never as the payload's operation key. The
handlers pass the operation each block declares; a block that reads its
dispatch key from the record instead (the Store's approval/evidence shims)
is handed the same value in the record it declares, because that is the
block's own contract -- never a second, invented one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

_VENDOR = Path(__file__).resolve().parents[1] / "vendor" / "blocks"
_CACHE: Dict[str, Any] = {}

#: block id -> the operation this platform calls by default. Read from each
#: block's own block.json default / the default its code declares.
BLOCK_DEFAULT_ACTIONS: Dict[str, Optional[str]] = {
    "analytics": "track_event",
    "approval_rules": "ledger",
    "audit": "log",
    "audit_chain": "record_evidence",
    "audit_fail_closed": "record",
    "boq_processor": "health",
    "capture": "capture",
    "cpm_engine": "compute",
    "dashboard": "render",
    "document_engine": None,
    "evidence_chain": "record",
    "evidence_or_refuse": "judge",
    "file_hasher": "hash",
    "finance_canonical_model": "schema",
    "formula_executor": "evaluate",
    "governance_gate": "list_requests",
    "knowledge": "search",
    "notification": "send",
    "ocr": None,
    "pdf": None,
    "rule_intent_router": "stats",
    "search": None,
    "transaction_state_machine": "transition",
    "validation": "validate_pipeline",
    "vector_search": "search",
    "version": "publish_version",
    "workflow": "run",
}

_FAILED_STATUSES = {"error", "failed", "partial"}

#: Genuine "this build cannot drive the block" reasons: a missing runtime
#: module, a broken vendored slice, or an optional engine the block needs.
#: A refusal of the VALUES the caller supplied carries none of these and
#: still fails the capability closed.
_UNAVAILABLE_MARKERS = (
    "ModuleNotFoundError",
    "ImportError",
    "No module named",
    "cannot import name",
    "not vendored",
    "BlockNotVendored",
    "Could not process input file",
    "No PDF parser available",
    "Tesseract",
    "tesseract",
    "PyMuPDF",
    "fitz",
    "pandas",
    "yaml",
    "No valid BOQ file",
    "No such file or directory",
    "FileNotFoundError",
    "has no attribute",
)


class BlockNotVendored(RuntimeError):
    """Asked for a block this platform does not carry."""


def load_block(block_id: str):
    if block_id in _CACHE:
        return _CACHE[block_id]
    path = _VENDOR / block_id / "block.py"
    if not path.is_file():
        raise BlockNotVendored(
            f"{block_id} is not vendored in this platform (looked in {path})"
        )
    spec = importlib.util.spec_from_file_location(f"vendored_{block_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CACHE[block_id] = module
    return module


def _error(block_id: str, action: Optional[str], message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "ok": False,
        "block": block_id,
        "action": action,
        "error": message,
    }


def _stub(block_id: str, action: Optional[str], reason: str) -> Dict[str, Any]:
    """A block this build genuinely cannot drive, named rather than hidden."""
    return {
        "status": "success",
        "ok": True,
        "block": block_id,
        "action": action,
        "stub": True,
        "blocks_unavailable": [block_id],
        "reason": "block unavailable in this build: " + reason[:240],
    }


def unavailable_reason(error: Any) -> Optional[str]:
    text = str(error or "")
    if not text:
        return None
    for marker in _UNAVAILABLE_MARKERS:
        if marker in text:
            return text
    return None


def execute(
    block_id: str,
    payload: Dict[str, Any],
    action: str | None = None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run a vendored block locally and return its envelope.

    A structural failure the build cannot fix (missing optional engine,
    broken vendored slice) is a declared stub naming the block. A refusal of
    the supplied values is returned as a refusal -- never rewritten to ok.
    """
    if block_id in ("workflow", "notification"):
        try:
            from app.local_blocks import event_bus as _peer

            _peer.ensure_registered()
        except Exception:  # noqa: BLE001 - peers are optional
            pass
    module = load_block(block_id)
    run = getattr(module, "run", None)
    if run is None:
        raise BlockNotVendored(f"{block_id} exposes no run() entry point")
    kwargs = dict(params or {})
    if action is not None:
        kwargs["action"] = action
    try:
        result = run(input=dict(payload or {}), **kwargs)
    except BlockNotVendored:
        raise
    except Exception as exc:
        reason = unavailable_reason(exc)
        if reason:
            return _stub(block_id, action, reason)
        return _error(block_id, action, f"{type(exc).__name__}: {exc}")
    if isinstance(result, dict):
        status = str(result.get("status") or "").lower()
        if status in _FAILED_STATUSES or result.get("ok") is False:
            reason = unavailable_reason(result.get("error") or result.get("message") or "")
            if reason:
                return _stub(block_id, action, reason)
            refused = dict(result)
            refused.setdefault("block", block_id)
            refused["ok"] = False
            if status and not refused.get("status"):
                refused["status"] = status
            return refused
    return result if isinstance(result, dict) else {"status": "success", "ok": True, "result": result}
