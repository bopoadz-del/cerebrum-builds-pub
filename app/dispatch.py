"""Block dispatch: one loader, one call shape, one failure vocabulary.

Every locked block is loaded from its own path (vendor/blocks/<id>/block.py)
and from nowhere else -- no copy, no re-implementation, no package the file
itself imports. The block's own ``run(**kwargs)`` is the entry point; the
action travels as a keyword, never inside the payload dict.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.block_inputs import BLOCK_DEFAULT_ACTIONS, default_block_action

ROOT = Path(__file__).resolve().parents[1]

_LOADED: Dict[str, Any] = {}
_LOCK = threading.RLock()

#: Distinguishes "no action named -> use the block's default" from an
#: explicit ``action=None`` ("this block takes no action").
_DEFAULT = object()


class BlockUnavailable(RuntimeError):
    """The locked block is not on disk where its lock pins it."""


class BlockFailure(RuntimeError):
    """A block ran and refused. The capability fails closed on it."""

    def __init__(self, block_id: str, message: str, answer: Optional[Dict[str, Any]] = None):
        super().__init__(f"{block_id}: {message}")
        self.block_id = block_id
        self.answer = answer or {}


def _product_roots():
    seen = []
    for candidate in (
        (os.environ.get("PRODUCT_ROOT") or "").strip(),
        str(ROOT),
        str(ROOT.parent / "product"),
    ):
        if not candidate:
            continue
        path = Path(candidate)
        if path in seen:
            continue
        seen.append(path)
        yield path


def _ensure_vendor_importable() -> Path:
    """Put the tree that contains ``vendor/`` on sys.path, once."""
    for root in _product_roots():
        if (root / "vendor" / "blocks").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root
    raise BlockUnavailable(
        "no vendor/blocks directory found; the locked blocks are not on disk"
    )


def block_path(block_id: str) -> Path:
    root = _ensure_vendor_importable()
    return root / "vendor" / "blocks" / str(block_id) / "block.py"


def _register_document_engine_alias() -> None:
    """The document_engine package loads its wrapper from
    ``document_engine_block.py``; the Store ships it as the package
    ``document_engine_block/``. Register the shipped package under the module
    name its own loader asks for, so the vendored class is the one used.
    """
    name = "vendor.cerebrum.blocks.document_engine_block"
    if name in sys.modules:
        return
    try:
        sys.modules[name] = importlib.import_module(name)
    except Exception:  # noqa: BLE001 - the block path below reports the truth
        pass


def load_block(block_id: str):
    """Load one locked block from its locked path."""
    key = str(block_id)
    with _LOCK:
        module = _LOADED.get(key)
        if module is not None:
            return module
        path = block_path(key)
        if not path.is_file():
            raise BlockUnavailable(f"locked block {key} is missing at {path}")
        _register_document_engine_alias()
        module = importlib.import_module(f"vendor.blocks.{key}.block")
        _LOADED[key] = module
        return module


def _is_failure(answer: Any) -> Optional[str]:
    if not isinstance(answer, dict):
        return None
    inner = answer.get("result") if isinstance(answer.get("result"), dict) else {}
    status = str(answer.get("status") or "")
    if status in {"error", "failed", "refused", "validation_error"}:
        return str(
            answer.get("error")
            or inner.get("error")
            or answer.get("detail")
            or status
        )
    inner_status = str(inner.get("status") or "")
    if inner_status in {"error", "failed", "refused", "validation_error"}:
        return str(inner.get("error") or answer.get("error") or inner_status)
    if answer.get("ok") is False:
        return str(answer.get("error") or "refused")
    if inner.get("ok") is False:
        return str(inner.get("error") or "refused")
    return None


def execute(
    block_id: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    action: Any = _DEFAULT,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run one block with a constructed input and its own action.

    Returns the block's answer. A refusal is returned as
    ``{"status": "error", "error": ...}`` so every caller refuses the same
    way; the block's own words travel with it.
    """
    key = str(block_id)
    module = load_block(key)
    call_kwargs: Dict[str, Any] = {"input": dict(payload or {})}
    resolved_action = BLOCK_DEFAULT_ACTIONS.get(key) if action is _DEFAULT else action
    if resolved_action is not None:
        call_kwargs["action"] = resolved_action
    call_kwargs.update(kwargs)
    try:
        answer = module.run(**call_kwargs)
    except Exception as exc:  # noqa: BLE001 - a block's refusal is data
        return {
            "status": "error",
            "block": key,
            "action": resolved_action,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(answer, dict):
        return {"status": "error", "block": key, "error": "block answered a non-mapping"}
    return answer


def run_block(block_id: str, payload: Optional[Dict[str, Any]] = None, *, action: Any = _DEFAULT) -> Dict[str, Any]:
    """execute(), but a refusal raises so the capability cannot answer ok:true
    over a failed block (F1)."""
    answer = execute(block_id, payload, action=action)
    failure = _is_failure(answer)
    if failure is not None:
        raise BlockFailure(str(block_id), failure, answer)
    return answer


def default_action(block_id: str) -> Optional[str]:
    return default_block_action(block_id)


def failure_of(answer: Any) -> Optional[str]:
    """The refusal a block's answer carries, or None when it succeeded."""
    return _is_failure(answer)


LOCKED_BLOCKS = tuple(sorted(BLOCK_DEFAULT_ACTIONS))


def verify_locked_blocks() -> None:
    """Start-up check: every locked block is on disk where its lock pins it.

    A missing one is an error raised here, never a fallback to a copy.
    """
    root = _ensure_vendor_importable()
    missing = [
        str(root / "vendor" / "blocks" / block / "block.py")
        for block in LOCKED_BLOCKS
        if not (root / "vendor" / "blocks" / block / "block.py").is_file()
    ]
    if missing:
        raise BlockUnavailable(
            "locked block(s) missing from their pinned path: " + ", ".join(missing)
        )


def loaded_blocks() -> Dict[str, Any]:
    return dict(_LOADED)
