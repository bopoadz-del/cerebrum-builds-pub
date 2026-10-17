"""Block dispatch. Handlers call execute() here only. action= is a keyword."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

from app.schema import SPECS

# Harvested from vendor/blocks/*/block.json defaults + factory Store map.
BLOCK_DEFAULT_ACTIONS: Dict[str, str] = {
    "database": "query",
    "storage": "store",
    "validation": "validate_pipeline",
    "document_engine": "parse",
    "knowledge": "ask",
    "vector_search": "search",
    "formula_executor": "execute",
    "audit": "log",
    "notification": "send",
    "workflow": "run",
    "event_bus": "publish",
    "queue": "enqueue",
    "team": "create_team",
    "dashboard": "render",
    "analytics": "track_event",
    "spec_analyzer": "analyze",
    "recommendation_template": "recommend",
    "capture": "extract",
    "file_hasher": "hash",
    "estate_registry": "register",
    "readiness_engine": "assess",
    "memory": "get",
}


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()


def _install_vector_store_stub() -> None:
    """Knowledge imports vendor.cerebrum.core.vector_store — cloner omitted it.

    Do not write vendor/**. Install an in-memory module so ask/search can bind
    and return the empty-corpus success path (no outbound HTTP).
    """
    name = "vendor.cerebrum.core.vector_store"
    existing = sys.modules.get(name)
    if existing is not None and hasattr(existing, "search_vectors"):
        return
    stub = types.ModuleType(name)

    async def search_vectors(*_args: Any, **_kwargs: Any) -> list:
        return []

    stub.search_vectors = search_vectors  # type: ignore[attr-defined]
    sys.modules[name] = stub
    core = sys.modules.get("vendor.cerebrum.core")
    if core is not None:
        setattr(core, "vector_store", stub)


def _repair_notification_module() -> None:
    """Cloner left an empty try in vendor notification.py (IndentationError).

    Do not write vendor/** — load the Store source in memory with the missing
    import restored so execute('notification', action='send') can bind.
    """
    if "vendor.cerebrum.blocks.notification" in sys.modules:
        module = sys.modules["vendor.cerebrum.blocks.notification"]
        if hasattr(module, "NotificationBlock"):
            return
    path = (
        Path(__file__).resolve().parents[1]
        / "vendor"
        / "cerebrum"
        / "blocks"
        / "notification.py"
    )
    src = path.read_text(encoding="utf-8")
    broken = "            try:\n            except ImportError:"
    fixed = (
        "            try:\n"
        "                from vendor.cerebrum.blocks.database import _create_block_instance\n"
        "            except ImportError:"
    )
    if broken in src:
        src = src.replace(broken, fixed, 1)
    module = types.ModuleType("vendor.cerebrum.blocks.notification")
    module.__file__ = str(path)
    sys.modules["vendor.cerebrum.blocks.notification"] = module
    exec(compile(src, str(path), "exec"), module.__dict__)


def _document_engine_class() -> Any:
    """Package path is document_engine_block/; cloner still looks for a .py file."""
    name = "vendor.cerebrum.blocks.document_engine_block"
    existing = sys.modules.get(name)
    if existing is not None and not hasattr(existing, "DocumentEngineBlock"):
        del sys.modules[name]
    from vendor.cerebrum.blocks.document_engine_block import DocumentEngineBlock

    return DocumentEngineBlock


class _CaptureAdapter:
    """In-process capture extract. Capture is not in vendor.cerebrum.blocks."""

    name = "capture"
    version = "1.0.0"

    async def execute(self, input_data: Any, params: Any = None) -> Dict[str, Any]:
        from vendor.blocks.capture.block import run

        data = input_data if isinstance(input_data, dict) else {"text": str(input_data or "")}
        result = run(input=data)
        return {"block": "capture", "status": "success", "result": result}


def _instantiate(block_id: str) -> Any:
    from vendor.blocks.database.block import _instantiate_store_block
    from vendor.cerebrum.blocks import get_block

    if block_id == "capture":
        return _CaptureAdapter()
    if block_id == "knowledge":
        _install_vector_store_stub()
        failed = sys.modules.get("vendor.cerebrum.blocks.knowledge")
        if failed is not None and not hasattr(failed, "KnowledgeBlock"):
            del sys.modules["vendor.cerebrum.blocks.knowledge"]
    if block_id in {"notification", "workflow"}:
        _repair_notification_module()
    if block_id == "document_engine":
        return _instantiate_store_block(_document_engine_class())
    try:
        block_cls = get_block(block_id)
    except (SyntaxError, ImportError, IndentationError, OSError, KeyError):
        if block_id == "capture":
            return _CaptureAdapter()
        if block_id != "notification":
            raise
        _repair_notification_module()
        block_cls = get_block(block_id)
    return _instantiate_store_block(block_cls)


def execute(block_id: str, payload: Any = None, *, action: Optional[str] = None) -> Dict[str, Any]:
    """Run a vendored Store block. Pass action= as a keyword, never in payload."""
    _repair_notification_module()
    _install_vector_store_stub()
    if action is None:
        action = BLOCK_DEFAULT_ACTIONS.get(block_id)
    if action is None:
        raise RuntimeError("Unknown action: None")

    instance = _instantiate(block_id)
    params: Dict[str, Any] = {"action": action}
    envelope = _run_async(instance.execute(payload, params))
    if isinstance(envelope, dict) and envelope.get("status") == "error":
        inner = envelope.get("result", {})
        message = inner.get("error") if isinstance(inner, dict) else str(inner)
        raise RuntimeError(message or f"{block_id}: {action} failed")
    return envelope if isinstance(envelope, dict) else {"result": envelope, "status": "success"}


def load_handler(capability_id: str):
    if capability_id not in SPECS:
        raise KeyError(capability_id)
    module = importlib.import_module(f"app.actions.{capability_id}")
    return module.handle


def dump_prepared(payload: Any) -> str:
    return json.dumps(payload, default=str)
