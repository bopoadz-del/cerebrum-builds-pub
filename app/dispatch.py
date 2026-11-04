"""Locked-block loader and the one execute() the actions call.

Each locked block is loaded from its pinned path under ``vendor/blocks`` and
from nowhere else.  A missing file is a start-up error, never a fallback.
The action a block dispatches on is its own contract: ``BLOCK_CONTRACTS``
records the default each block's code declares and whether that block reads
``action`` from its input record rather than from params.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "vendor" / "blocks"

BLOCK_IDS = [
    "analytics",
    "approval_rules",
    "audit",
    "audit_chain",
    "boq_processor",
    "cpm_engine",
    "dashboard",
    "document_engine",
    "evidence_chain",
    "evidence_or_refuse",
    "finance_canonical_model",
    "finance_planning",
    "finance_reconciliation",
    "formula_executor",
    "governance_gate",
    "knowledge",
    "pdf",
    "portfolio_rollup",
    "regulatory_chunker",
    "storage",
    "transaction_state_machine",
    "validation",
    "version",
    "version_diff",
    "workflow",
]

#: action = the operation the block's own code defaults to (block.json
#: ``inputs[name=action].default``, else the default its process() declares).
#: action_in_input = the block reads the operation from its input record.
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "analytics": {"action": "track_event", "action_in_input": False},
    "approval_rules": {"action": "ingest", "action_in_input": True},
    "audit": {"action": "log", "action_in_input": False},
    "audit_chain": {"action": "record_evidence", "action_in_input": False},
    "boq_processor": {"action": "status", "action_in_input": False},
    "cpm_engine": {"action": "compute", "action_in_input": False},
    "dashboard": {"action": "render", "action_in_input": False},
    "document_engine": {"action": None, "action_in_input": False},
    "evidence_chain": {"action": "record", "action_in_input": True},
    "evidence_or_refuse": {"action": "judge", "action_in_input": True},
    "finance_canonical_model": {"action": None, "action_in_input": False},
    "finance_planning": {"action": "create_budget", "action_in_input": False},
    "finance_reconciliation": {"action": None, "action_in_input": False},
    "formula_executor": {"action": None, "action_in_input": False},
    "governance_gate": {"action": "create_request", "action_in_input": True},
    "knowledge": {"action": "search", "action_in_input": False,
                  "params_from_input": ["project_id", "top_k"]},
    "pdf": {"action": None, "action_in_input": False},
    "portfolio_rollup": {"action": "aggregate", "action_in_input": False},
    "regulatory_chunker": {"action": "chunk_regulatory", "action_in_input": False},
    "storage": {"action": "store", "action_in_input": False,
                "config_from_input": ["data_dir", "backend"]},
    "transaction_state_machine": {"action": None, "action_in_input": False},
    "validation": {"action": "validate_pipeline", "action_in_input": False},
    "version": {"action": "publish_version", "action_in_input": False},
    "version_diff": {"action": None, "action_in_input": False},
    "workflow": {"action": "run", "action_in_input": False},
}

_BLOCKS: Dict[str, Any] = {}

#: Refusal statuses a block answers with.  Anything else is an answer.
_REFUSAL_STATUSES = frozenset({"error", "failed", "fail", "refused", "validation_error", "unsupported"})


def _install_core_shims() -> None:
    try:
        from app.core_shims import install as _install_shims
    except Exception:
        return
    _install_shims()


def _preload_shadowed_blocks() -> None:
    """Import the document_engine wrapper package before the package that
    shadows it.

    ``vendor/cerebrum/blocks/document_engine`` looks for a sibling
    ``document_engine_block.py``; the wrapper ships as a package directory, so
    importing the package first puts it in ``sys.modules`` under the name the
    shadowing module reuses and both refer to the same class object.
    """
    try:
        import vendor.cerebrum.blocks.document_engine_block  # noqa: F401
    except Exception:
        return


def locked_path(block_id: str) -> Path:
    return VENDOR_ROOT / str(block_id) / "block.py"


def load_block(block_id: str):
    """Load one locked block from its pinned file; error when absent."""
    name = str(block_id)
    if name in _BLOCKS:
        return _BLOCKS[name]
    _preload_shadowed_blocks()
    _install_core_shims()
    path = locked_path(name)
    if not path.is_file():
        raise RuntimeError(
            "locked block %r is missing from %s -- the build did not copy it"
            % (name, path)
        )
    module_name = "vendor_locked_blocks._%s" % name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load locked block %r from %s" % (name, path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    loaded_from = Path(getattr(module, "__file__", "")).resolve()
    if loaded_from != path.resolve():
        raise RuntimeError(
            "block %r loaded from %s, not its locked path %s" % (name, loaded_from, path)
        )
    _BLOCKS[name] = module
    return module


def execute(
    block_id: str,
    payload: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a block through its adapter, passing action= as a keyword."""
    module = load_block(block_id)
    contract = BLOCK_CONTRACTS.get(str(block_id)) or {}
    data: Dict[str, Any] = dict(payload or {})
    if action is not None and contract.get("action_in_input"):
        data.setdefault("action", action)
    kwargs: Dict[str, Any] = {"input": data}
    if action is not None:
        kwargs["action"] = action
    # A block that reads its configuration from params (not from its input
    # record) needs those keys where its own contract looks for them.
    for key in contract.get("params_from_input") or []:
        if key in data:
            kwargs[key] = data[key]
    config_keys = list(contract.get("config_from_input") or [])
    if config_keys:
        return _run_configured(block_id, data, action, config_keys)
    runner = getattr(module, "run", None)
    if runner is None:  # a class, not an adapter module
        raise RuntimeError("locked block %r exposes no run()" % block_id)
    try:
        result = runner(**kwargs)
    except TypeError:
        result = runner(input=data)
    if not isinstance(result, dict):
        return {"status": "error", "block": block_id, "error": "block returned no mapping"}
    return result


def _run_configured(
    block_id: str,
    data: Dict[str, Any],
    action: Optional[str],
    config_keys: list,
) -> Dict[str, Any]:
    """Instantiate a block whose storage root is configuration, not input.

    The locked adapters build their block with default configuration, which
    would put a second copy of the store on the process's working directory.
    These keys name where the block keeps its data, so the instance is built
    with the platform's own root and then run.
    """
    import asyncio
    import concurrent.futures

    from vendor.cerebrum.blocks import get_block

    config = {key: data[key] for key in config_keys if key in data}
    instance = get_block(block_id)(config=config)
    params: Dict[str, Any] = {}
    if action is not None:
        params["action"] = action
    coro = instance.execute(dict(data), params)

    async def _await_result():
        return await coro

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        result = asyncio.run(_await_result())
    else:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, _await_result()).result()
    if isinstance(result, dict) and "result" in result and result.get("status") in ("success", "ok"):
        inner = result.get("result")
        return inner if isinstance(inner, dict) else result
    return result if isinstance(result, dict) else {"status": "error", "error": "block returned no mapping"}


def refused(result: Any) -> Optional[str]:
    """The block's refusal as a string, or None when it answered."""
    if not isinstance(result, dict):
        return "block returned no mapping"
    status = str(result.get("status") or "").lower()
    if result.get("ok") is False or status in _REFUSAL_STATUSES:
        return str(result.get("error") or result.get("detail") or status or "refused")
    return None
