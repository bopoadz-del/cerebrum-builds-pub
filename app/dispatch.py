"""Loader and caller for the locked Store blocks.

Each block is loaded from its locked path only: vendor/blocks/<id>/block.py.
A locked block that is absent from that path is an error raised at start-up,
never a fallback or a local re-implementation.

Two vendored blocks in this lockfile address their runtime module by a path
that the vendored package layout does not expose (the document_engine wrapper
file lives in the package directory; the knowledge block imports the core
vector store). The loader aliases the module the block itself asks for; it
does not replace the block or its path.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]

LOCKED_PATHS: Dict[str, str] = {
    block: "vendor/blocks/%s/block.py" % block
    for block in (
        "analytics",
        "approval_rules",
        "audit_chain",
        "boq_processor",
        "cpm_engine",
        "dashboard",
        "document_engine",
        "evidence_chain",
        "evidence_or_refuse",
        "evidence_verifier",
        "file_hasher",
        "finance_canonical_model",
        "finance_reconciliation_workflow",
        "formula_executor",
        "knowledge",
        "notification",
        "review",
        "search",
        "transaction_state_machine",
        "vector_search",
        "version_diff",
        "workflow",
    )
}

#: The action each block's own contract declares (block.json default, else the
#: default its code reads). None means the block dispatches on no action.
BLOCK_DEFAULT_ACTIONS: Dict[str, Optional[str]] = {
    "analytics": "track_event",
    "approval_rules": "ingest",
    "audit_chain": "record_evidence",
    "boq_processor": None,
    "cpm_engine": "compute",
    "dashboard": "render",
    "document_engine": None,
    "evidence_chain": "record",
    "evidence_or_refuse": "judge",
    "evidence_verifier": "store",
    "file_hasher": "hash",
    "finance_canonical_model": "schema",
    "finance_reconciliation_workflow": "create_run",
    "formula_executor": None,
    "knowledge": "ask",
    "notification": "send",
    "review": "get_reviews",
    "search": None,
    "transaction_state_machine": "transition",
    "vector_search": None,
    "version_diff": "diff",
    "workflow": "run",
}

#: Declared input keys each block reads at its top level (used to classify an
#: envelope-shape refusal). All locked blocks here read their record flat.
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {
    block: {"input_keys_read_by_block": []} for block in LOCKED_PATHS
}

_MODULES: Dict[str, Any] = {}
_SHIMS_DONE = False


def _vendor_on_path() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _install_runtime_shims() -> None:
    """Give the two blocks the module path they resolve, from the vendor tree."""
    global _SHIMS_DONE
    if _SHIMS_DONE:
        return
    _vendor_on_path()
    try:
        import vendor.cerebrum.core as core

        if "vendor.cerebrum.core.vector_store" not in sys.modules:
            shim = types.ModuleType("vendor.cerebrum.core.vector_store")

            async def search_vectors(project_id, query, top_k=5, threshold=0.0):
                from app import retrieval
                from app.actions import _support

                if str(project_id) != _support.tenant_id():
                    return []
                hits = [
                    hit
                    for hit in retrieval.search(str(project_id), str(query), top_k=top_k)
                    if float(hit.get("score") or 0.0) >= float(threshold or 0.0)
                ]
                return [
                    {
                        "id": "%s#%s" % (hit.get("source"), hit.get("seq")),
                        "text": hit.get("text"),
                        "score": hit.get("score"),
                        "metadata": {"source": hit.get("source")},
                    }
                    for hit in hits
                ]

            shim.search_vectors = search_vectors
            sys.modules["vendor.cerebrum.core.vector_store"] = shim
            setattr(core, "vector_store", shim)
    except Exception:  # noqa: BLE001 -- the block's own import decides
        pass
    try:
        if "vendor.cerebrum.blocks.document_engine_block" not in sys.modules:
            module = importlib.import_module("vendor.cerebrum.blocks.document_engine_block")
            sys.modules["vendor.cerebrum.blocks.document_engine_block"] = module
    except Exception:  # noqa: BLE001 -- the block's own import decides
        pass
    _SHIMS_DONE = True


def load_block(block_id: str):
    """Load one locked block from the one path the lockfile pins it to."""
    if block_id in _MODULES:
        return _MODULES[block_id]
    relative = LOCKED_PATHS.get(block_id)
    if relative is None:
        raise RuntimeError("block %s is not in the Store registry" % block_id)
    path = ROOT / relative
    if not path.is_file():
        raise RuntimeError(
            "locked block %s is missing from %s -- the product tree was not "
            "laid out with its vendor blocks" % (block_id, relative)
        )
    _install_runtime_shims()
    spec = importlib.util.spec_from_file_location(
        "vendor_locked_%s" % block_id, str(path)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load locked block %s from %s" % (block_id, relative))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise RuntimeError("locked block %s exposes no run()" % block_id)
    _MODULES[block_id] = module
    return module


NON_FAILURE_STATUSES = frozenset({"", "ok", "success", "no_data", "skipped", "completed"})
FAILURE_STATUSES = frozenset(
    {"error", "failed", "refused", "partial", "validation_error", "unavailable", "unsupported"}
)


def failed(answer: Any, block_id: str = "") -> bool:
    """True when a block answer is a refusal or an unknown answer shape."""
    if answer is None:
        return True
    if not isinstance(answer, dict):
        return False
    if answer.get("ok") is False:
        return True
    status = str(answer.get("status") or "").lower()
    if status == "fail":
        return block_id != "validation"
    if status in FAILURE_STATUSES:
        return True
    if answer.get("error") and not status:
        return True
    return False


def error_text(answer: Any) -> str:
    if isinstance(answer, dict):
        return str(answer.get("error") or answer.get("detail") or "block refused")[:300]
    return str(answer)[:300]


def execute(
    block_id: str,
    payload: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Invoke one locked block with action= as a keyword, never in payload."""
    try:
        module = load_block(block_id)
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 -- an unloadable block is a typed answer
        return {
            "status": "error",
            "error_kind": "unavailable",
            "block": block_id,
            "action": action,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }
    call = dict(payload or {})
    call.update(kwargs)
    if action is not None:
        call["action"] = action
    try:
        answer = module.run(**call)
    except Exception as exc:  # noqa: BLE001 -- a block failure is a typed answer
        text = str(exc)
        unavailable = isinstance(exc, ModuleNotFoundError)
        return {
            "status": "error",
            "error_kind": "unavailable" if unavailable else "block_error",
            "block": block_id,
            "action": action,
            "error": "%s: %s" % (type(exc).__name__, text),
        }
    if not isinstance(answer, dict):
        return {"status": "ok", "block": block_id, "result": answer}
    answer.setdefault("block", block_id)
    if action is not None:
        answer.setdefault("action", action)
    return answer
