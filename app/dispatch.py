"""Locked-block loader and pure action dispatch.

Every locked block is read from the one file blocks.lock.json names for it.
There is no fallback: a missing locked path is an error at start-up. Block
actions are passed as the ``action=`` keyword, never inside the payload dict
(the one in-band exception is approval_rules, whose own contract reads its
operation out of the payload -- it is marked here, not guessed downstream).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
BLOCK_ROOT = VENDOR / "blocks"

LOCKED_BLOCKS = {
    "approval_rules": BLOCK_ROOT / "approval_rules" / "block.py",
    "boq_processor": BLOCK_ROOT / "boq_processor" / "block.py",
    "document_engine": BLOCK_ROOT / "document_engine" / "block.py",
    "finance_reconciliation": BLOCK_ROOT / "finance_reconciliation" / "block.py",
    "formula_executor": BLOCK_ROOT / "formula_executor" / "block.py",
    "search": BLOCK_ROOT / "search" / "block.py",
    "validation": BLOCK_ROOT / "validation" / "block.py",
    "version": BLOCK_ROOT / "version" / "block.py",
    "workflow": BLOCK_ROOT / "workflow" / "block.py",
}

#: Read from each block's own block.json default, else the first action its
#: code compares against, else None (the block dispatches on no action).
BLOCK_DEFAULT_ACTIONS = {
    "approval_rules": "ingest",
    "boq_processor": None,
    "document_engine": None,
    "finance_reconciliation": None,
    "formula_executor": None,
    "search": None,
    "validation": "validate_pipeline",
    "version": "publish_version",
    "workflow": "run",
}

#: Blocks whose own contract reads the operation from the input payload.
IN_BAND_ACTIONS = {"approval_rules"}

BLOCK_CONTRACTS = {
    "approval_rules": {
        "input_keys_read_by_block": ["action", "project_id", "source_doc", "extracted", "rule_id", "approve", "reviewer"],
        "action_in_band": True,
    },
    "boq_processor": {"input_keys_read_by_block": ["file_path", "text", "input"]},
    "document_engine": {"input_keys_read_by_block": ["text", "brief", "pdf_path", "docx_path", "xlsx_path"]},
    "finance_reconciliation": {
        "input_keys_read_by_block": ["left_records", "right_records", "group_by", "amount_field", "tolerance"],
    },
    "formula_executor": {
        "input_keys_read_by_block": ["formula_key", "formula_description", "input_values", "custom_code", "operation"],
    },
    "search": {"input_keys_read_by_block": ["query", "text", "input"]},
    "validation": {"input_keys_read_by_block": ["item", "context"]},
    "version": {"input_keys_read_by_block": ["block_id", "version", "changelog", "dependencies", "current_stack"]},
    "workflow": {"input_keys_read_by_block": ["pipeline_id", "steps", "trigger", "timeout"]},
}

_MODULES: dict = {}


def _ensure_paths() -> None:
    for entry in (str(ROOT), str(VENDOR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def load_block(block_id: str):
    if block_id in _MODULES:
        return _MODULES[block_id]
    if block_id not in LOCKED_BLOCKS:
        raise RuntimeError("block not locked for this product: " + str(block_id))
    path = LOCKED_BLOCKS[block_id]
    if not path.is_file():
        raise RuntimeError("locked block missing at " + str(path) + " (" + block_id + ")")
    _ensure_paths()
    module_name = "locked_block_" + block_id
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("locked block cannot be loaded: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULES[block_id] = module
    return module


def default_block_action(block_id: str) -> Optional[str]:
    return BLOCK_DEFAULT_ACTIONS.get(block_id)


def execute(block_id: str, payload: dict | None = None, action: str | None = None, params: dict | None = None) -> dict:
    module = load_block(block_id)
    runner = getattr(module, "run", None)
    if not callable(runner):
        raise RuntimeError("locked block " + block_id + " exports no run()")
    data: dict = dict(payload or {})
    if block_id in IN_BAND_ACTIONS:
        data.setdefault("action", action or BLOCK_DEFAULT_ACTIONS.get(block_id))
    call_params = dict(params or {})
    if action is not None:
        call_params["action"] = action
    elif BLOCK_DEFAULT_ACTIONS.get(block_id) is not None:
        call_params["action"] = BLOCK_DEFAULT_ACTIONS[block_id]
    result = runner(input=data, **call_params)
    if not isinstance(result, dict):
        raise RuntimeError("locked block " + block_id + " answered no mapping")
    return result


def block_manifest(block_id: str) -> dict:
    path = LOCKED_BLOCKS[block_id].parent / "block.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
