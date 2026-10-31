"""Load and execute a vendored Store block from its locked path.

Blocks are called through ``execute(block_id, payload, action=...)``. The
action is always a keyword; it never travels inside the payload record.
"""

from __future__ import annotations

import importlib.util
import importlib
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
VENDOR_BLOCKS = ROOT / "vendor" / "blocks"

# Action contracts read from the bound blocks' block.json / code defaults.
BLOCK_DEFAULT_ACTIONS: Dict[str, Optional[str]] = {
    "knowledge": "ask",
    "search": None,
    "vector_search": None,
    "llm_enhancer": "status",
    "ocr": None,
    "finance_canonical_model": None,
    "finance_import": None,
    "finance_data_quality": None,
    "finance_reconciliation": None,
    "validation": "validate_pipeline",
    "approval_rules": None,
    "notification": "send",
    "email": "send",
    "analytics": "track_event",
    "dashboard": "render",
    "version_diff": None,
    "microsoft_365": None,
    "audit": "log",
    "onedrive": None,
    "capture": None,
    "ingestion_provenance": None,
    "pdf": None,
    "aesthetic_kit": None,
    "auth": "validate",
    "user_auth": None,
    "multi_tenant_rbac": None,
    "sap_odata_connector": None,
}

# Keys the block implementation reads at the top level of its input record.
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "vector_search": {"input_keys_read_by_block": ["query", "text", "input", "operation", "collection"]},
    "search": {"input_keys_read_by_block": ["query", "text", "input"]},
    "notification": {"input_keys_read_by_block": ["channel", "message", "to", "subject", "block", "tool", "payload"]},
    "email": {"input_keys_read_by_block": ["email", "to", "subject", "body"]},
    "audit": {"input_keys_read_by_block": ["event", "actor", "resource_type", "resource_id", "details"]},
    "version_diff": {"input_keys_read_by_block": ["findings_v1", "findings_v2", "proposals", "diff"]},
    "microsoft_365": {"input_keys_read_by_block": ["action", "connection_id", "organization_id"]},
    "approval_rules": {"input_keys_read_by_block": ["action", "project_id", "source_doc", "rule_id"]},
    "ingestion_provenance": {"input_keys_read_by_block": ["action", "source", "pages"]},
}

_LOADED: Dict[str, Any] = {}


def _install_optional_vector_store() -> None:
    """The vendored knowledge block imports ``vector_store`` from the core
    package. That module is an optional pgvector foundation and fail-soft by
    design; when the product tree omits it, register the same fail-soft
    surface (empty retrieval, no network) instead of letting one optional
    dependency make the block unloadable.
    """
    name = "vendor.cerebrum.core.vector_store"
    if name in sys.modules:
        return
    try:
        importlib.import_module(name)
        return
    except ImportError:
        pass
    module = types.ModuleType(name)

    async def search_vectors(project_id=None, query=None, top_k=5, threshold=0.0, **_kw):
        return []

    async def index_vectors(project_id=None, rows=None, **_kw):
        return {"indexed": 0}

    module.search_vectors = search_vectors
    module.index_vectors = index_vectors
    module.DRIVER_AVAILABLE = False
    sys.modules[name] = module
    try:
        import vendor.cerebrum.core as core

        setattr(core, "vector_store", module)
    except ImportError:
        pass


def block_path(block_id: str) -> Path:
    return VENDOR_BLOCKS / str(block_id) / "block.py"


def load_block(block_id: str):
    """Load vendor/blocks/<id>/block.py. A missing locked path is an error."""
    identifier = str(block_id)
    _install_optional_vector_store()
    if identifier in _LOADED:
        return _LOADED[identifier]
    path = block_path(identifier)
    if not path.is_file():
        raise RuntimeError(f"locked block {identifier} absent from {path}")
    spec = importlib.util.spec_from_file_location(f"vendor_block_{identifier}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"locked block {identifier} cannot be loaded from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOADED[identifier] = module
    return module


def execute(block_id: str, payload: Any = None, *, action: Optional[str] = None,
            params: Optional[Dict[str, Any]] = None, **extra: Any) -> Dict[str, Any]:
    module = load_block(block_id)
    options: Dict[str, Any] = dict(params or {})
    options.update(extra)
    if action is not None:
        options["action"] = action
    options["input"] = payload if payload is not None else {}
    return module.run(**options)
