"""Locked-block loader and the one execute() the actions call.

``load_block`` reads only the path blocks.lock.json pins for the block.  The
locked file is the adapter the Factory shipped; there is no fallback to a
copy, a re-implementation or a package lookup when it is absent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "blocks.lock.json"
_MODULES: Dict[str, Any] = {}


def _locked_paths() -> Dict[str, Path]:
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("blocks.lock.json is unreadable: %s" % exc) from exc
    blocks = data.get("blocks") or {}
    out: Dict[str, Path] = {}
    for block_id, meta in blocks.items():
        rel = (meta or {}).get("path")
        if not rel:
            raise RuntimeError("locked block %r has no path" % (block_id,))
        out[str(block_id)] = ROOT / rel / "block.py"
    return out


LOCKED_PATHS = _locked_paths()


def load_block(block_id: str):
    """Load one locked block adapter from its pinned file, and nowhere else."""
    key = str(block_id)
    if key in _MODULES:
        return _MODULES[key]
    path = LOCKED_PATHS.get(key)
    if path is None:
        raise RuntimeError("block %r is not in blocks.lock.json" % key)
    if not path.is_file():
        raise RuntimeError("locked block %r is absent from %s" % (key, path))
    module_name = "locked_block_" + key
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("locked block %r could not be loaded" % key)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise RuntimeError("locked block %r declares no run()" % key)
    hal = getattr(module, "_OfflineHal", None)
    if hal is not None and not hasattr(hal, "detect"):
        # The adapter promises a HAL; config's constructor reads its
        # hardware profile. Give the in-process HAL that one method.
        from types import SimpleNamespace

        hal.detect = lambda self: SimpleNamespace(value="cpu", name="cpu")
    _MODULES[key] = module
    return module


def execute(block_id: str, payload: Optional[Dict[str, Any]] = None,
            action: Optional[str] = None, params: Optional[Dict[str, Any]] = None,
            **kwargs: Any) -> Dict[str, Any]:
    """Run a locked block.  Dispatch is by the action= KEYWORD, never a
    payload key.  A block refusal is returned as data so the capability can
    fail closed and persist nothing."""
    block = load_block(block_id)
    call: Dict[str, Any] = {"input": dict(payload or {})}
    if action is not None:
        call["action"] = action
    for key, value in (params or {}).items():
        call[key] = value
    for key, value in kwargs.items():
        call[key] = value
    try:
        result = block.run(**call)
    except Exception as exc:  # a block refusal is data, never a 500
        return {
            "status": "error",
            "block": str(block_id),
            "action": action,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }
    if not isinstance(result, dict):
        return {"status": "error", "block": str(block_id), "error": "block returned a non-mapping"}
    return result


def _block_instance(block_id: str, config: Optional[Dict[str, Any]] = None):
    """Build one instance of a locked block through the block's own adapter.

    The adapter's ``run()`` builds a fresh instance per call, which is right
    for a pure decision but cannot carry an escrow hold into its release or a
    registered job into its match.  These helpers reuse the adapter's own
    constructor and async runner so a sequence is still the locked block's
    own code, never a re-implementation.
    """
    module = load_block(block_id)
    getter = getattr(module, "get_block", None)
    if not callable(getter):
        raise RuntimeError("locked block %r exposes no class registry" % block_id)
    block_cls = getter(block_id)
    if config:
        hal = module._offline_hal()
        instance = block_cls(hal, dict(config))
        prepare = getattr(module, "_ensure_store_block_ready", None)
        if callable(prepare):
            instance = prepare(instance)
    else:
        instance = module._instantiate_store_block(block_cls)
    return module, instance


def execute_sequence(block_id: str, steps: List[Dict[str, Any]],
                     config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run several operations on ONE block instance, returning the last result.

    Each step is ``{"input": {...}, "action": ...}``.  A refusal stops the
    sequence and is returned as data, exactly like ``execute()``.
    """
    try:
        module, instance = _block_instance(block_id, config)
        runner = getattr(module, "_run_async")
        last: Dict[str, Any] = {}
        for step in steps:
            payload = dict(step.get("input") or {})
            params = {key: value for key, value in step.items() if key != "input"}
            try:
                envelope = runner(instance.execute(payload, params))
            except Exception as exc:
                return {"status": "error", "block": str(block_id),
                        "action": params.get("action"),
                        "error": "%s: %s" % (type(exc).__name__, exc)}
            if not isinstance(envelope, dict):
                return {"status": "error", "block": str(block_id),
                        "error": "block returned a non-mapping"}
            if envelope.get("status") == "error":
                return envelope
            result = envelope.get("result", envelope)
            last = dict(result) if isinstance(result, dict) else {"result": result}
        last.setdefault("block", str(block_id))
        return last
    except Exception as exc:
        return {"status": "error", "block": str(block_id),
                "error": "%s: %s" % (type(exc).__name__, exc)}
