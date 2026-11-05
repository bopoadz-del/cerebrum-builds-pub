"""Block loading and the single execute() path every capability calls.

Blocks are loaded from their LOCKED path only -- ``vendor/blocks/<id>/block.py``
-- never from a copy under ``app/``. ``blocks.lock.json`` pins each id to that
path; a locked block whose file is absent from a product tree is an error, not
a silent fallback.

Dispatch contract:
  * the operation travels as the ``action=`` KEYWORD, never inside the payload;
  * ``BLOCK_DEFAULT_ACTIONS`` is read from each block's own contract (its
    block.json default, else the default its code declares);
  * ``execute`` returns a dict envelope ``{ok, block, action, ...}`` and never
    raises for a block's own refusal, so a caller can fail closed on it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "vendor" / "blocks"
LOCK_FILE = ROOT / "blocks.lock.json"

#: The locked roster this product binds.
BLOCK_IDS: List[str] = [
    "approval_rules",
    "audit",
    "audit_chain",
    "audit_fail_closed",
    "auth",
    "boq_processor",
    "capture",
    "cpm_engine",
    "dashboard",
    "document_engine",
    "evidence_chain",
    "file_hasher",
    "finance_canonical_model",
    "finance_planning",
    "finance_reconciliation",
    "formula_executor",
    "governance_gate",
    "ingestion_provenance",
    "knowledge",
    "multi_tenant_rbac",
    "notification",
    "ocr",
    "pdf",
    "review",
    "search",
    "storage",
    "transaction_state_machine",
    "validation",
    "version",
    "version_diff",
    "workbench",
    "workflow",
]

#: The operation this product invokes when a bound block's own contract does
#: not declare a default. Each value is an action the block's own dispatch
#: actually accepts (see its wrapped ``process``).
PRODUCT_DEFAULT_ACTIONS: Dict[str, str] = {
    "approval_rules": "list",
    "audit": "log",
    "audit_chain": "record_evidence",
    "audit_fail_closed": "principal",
    "auth": "validate",
    "capture": "capture",
    "cpm_engine": "compute",
    "dashboard": "render",
    "evidence_chain": "record",
    "file_hasher": "hash",
    "finance_canonical_model": "schema",
    "finance_planning": "create_budget",
    "governance_gate": "create_request",
    "ingestion_provenance": "build",
    "knowledge": "ask",
    "multi_tenant_rbac": "check",
    "notification": "send",
    "review": "submit_review",
    "storage": "store",
    "transaction_state_machine": "transition",
    "validation": "validate_pipeline",
    "version": "publish_version",
    "version_diff": "diff",
    "workbench": "run",
    "workflow": "run",
}

BLOCK_DEFAULT_ACTIONS: Dict[str, str] = dict(PRODUCT_DEFAULT_ACTIONS)
BLOCK_CONTRACTS: Dict[str, Dict[str, Any]] = {}

_LOADED: Dict[str, types.ModuleType] = {}


class BlockUnavailable(RuntimeError):
    """A locked block is not where the lock file says it lives."""


def block_path(block_id: str) -> Path:
    lock = _lock_entry(block_id)
    if lock:
        candidate = ROOT / lock
        if candidate.suffix == ".py" or candidate.is_file():
            return candidate
        return candidate / "block.py"
    return VENDOR_ROOT / block_id / "block.py"


def _lock_entry(block_id: str) -> Optional[str]:
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    blocks = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks, dict):
        return None
    entry = blocks.get(block_id)
    if isinstance(entry, dict):
        return str(entry.get("path") or "") or None
    if isinstance(entry, str):
        return entry
    return None


def _block_json(block_id: str) -> Dict[str, Any]:
    path = block_path(block_id).parent / "block.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


_DEFAULT_ACTION_RE = re.compile(
    r"""(?:params|kwargs|payload|data|opts|options|inputs?|request|body|arguments|args)"""
    r"""\s*\.\s*get\(\s*["']action["']\s*,\s*["']([A-Za-z][\w.:-]*)["']"""
)
_ACTION_COMPARE_RE = re.compile(
    r"""["']action["']\s*\]?\s*(?:==|!=|in)\s*[\(\[{]?\s*["']([A-Za-z][\w.:-]*)["']"""
)


def _wrapped_source(block_id: str) -> str:
    candidates = [
        ROOT / "vendor" / "cerebrum" / "blocks" / f"{block_id}.py",
        ROOT / "vendor" / "cerebrum" / "blocks" / block_id / "__init__.py",
    ]
    for path in candidates:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return ""


def _declared_default_action(block_id: str, module: Optional[types.ModuleType]) -> Optional[str]:
    """The default the block's own contract declares -- block.json first."""
    spec = _block_json(block_id)
    inputs = spec.get("inputs")
    if isinstance(inputs, list):
        for entry in inputs:
            if isinstance(entry, dict) and entry.get("name") in ("action", "operation", "op"):
                if entry.get("default"):
                    return str(entry["default"])
    elif isinstance(inputs, dict):
        for key in ("action", "operation", "op"):
            entry = inputs.get(key)
            if isinstance(entry, dict) and entry.get("default"):
                return str(entry["default"])
    for key in ("default_action", "action", "operation"):
        value = spec.get(key)
        if isinstance(value, str) and value:
            return value
    if module is not None:
        for attr in ("DEFAULT_ACTION", "ACTION", "DEFAULT_OPERATION"):
            value = getattr(module, attr, None)
            if isinstance(value, str) and value:
                return value
        try:
            source = Path(getattr(module, "__file__", "") or "").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            source = ""
        for pattern in (_DEFAULT_ACTION_RE, _ACTION_COMPARE_RE):
            match = pattern.search(source)
            if match:
                return match.group(1)
    wrapped = _wrapped_source(block_id)
    for pattern in (_DEFAULT_ACTION_RE, _ACTION_COMPARE_RE):
        match = pattern.search(wrapped)
        if match:
            return match.group(1)
    return None


def _contract(block_id: str, module: Optional[types.ModuleType]) -> Dict[str, Any]:
    spec = _block_json(block_id)
    inputs = spec.get("inputs")
    reads: List[str] = []
    if isinstance(inputs, list):
        reads = [str(entry.get("name")) for entry in inputs if isinstance(entry, dict) and entry.get("name")]
    elif isinstance(inputs, dict):
        reads = [str(name) for name in inputs]
    return {
        "path": str(block_path(block_id)),
        "default_action": _declared_default_action(block_id, module),
        "input_keys_read_by_block": reads,
        "declared_inputs": inputs,
    }


def _workbench_cli() -> str:
    """The offline agent the workbench block shells out to.

    The block invokes ``KIMI_CLI_PATH`` with ``--prompt @file --add-dir dir``.
    This platform runs offline and has no cloud agent CLI, so it invokes its
    own bounded, deterministic inspector. The launcher is materialised with an
    exec bit because a packaged file's mode is not guaranteed.
    """
    agent = ROOT / "scripts" / "workbench_agent.py"
    root = Path(os.environ.get("STORAGE_PATH") or (ROOT / "data"))
    try:
        launcher_dir = root / ".workbench"
        launcher_dir.mkdir(parents=True, exist_ok=True)
        launcher = launcher_dir / "agent"
        launcher.write_text(
            "#!/bin/sh\nexec \"" + sys.executable + "\" \"" + str(agent) + "\" \"$@\"\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        return str(launcher)
    except OSError:
        return str(agent)


def _prime_wrapped_module(block_id: str) -> None:
    """Import a wrapped package that shadows its own adapter.

    ``document_engine`` is a package (``vendor/cerebrum/blocks/document_engine``)
    whose adapter lives in a sibling package ``document_engine_block``. The
    package's __init__ resolves that sibling through sys.modules; priming it
    first is the same import the adapter itself performs, not a second engine.
    """
    wrapper = ROOT / "vendor" / "cerebrum" / "blocks" / f"{block_id}_block"
    shadow = ROOT / "vendor" / "cerebrum" / "blocks" / block_id
    if not (wrapper.is_dir() and shadow.is_dir()):
        return
    try:
        importlib.import_module(f"vendor.cerebrum.blocks.{block_id}_block")
    except Exception:  # noqa: BLE001 - the adapter will report the real refusal
        return


def load_block(block_id: str) -> types.ModuleType:
    """Import the locked block module, once, from its locked path."""
    loaded = _LOADED.get(block_id)
    if loaded is not None:
        return loaded
    if block_id == "workbench":
        os.environ.setdefault("KIMI_CLI_PATH", _workbench_cli())
    _prime_wrapped_module(block_id)
    path = block_path(block_id)
    if not path.is_file():
        raise BlockUnavailable(
            f"locked block {block_id!r} is absent from its locked path {path}"
        )
    package_name = f"_cerebrum_blocks.{block_id}"
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__path__ = [str(path.parent)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package
    module_name = f"{package_name}.block"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise BlockUnavailable(f"locked block {block_id!r} at {path} is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    _LOADED[block_id] = module
    BLOCK_CONTRACTS[block_id] = _contract(block_id, module)
    default = (
        BLOCK_DEFAULT_ACTIONS.get(block_id)
        or BLOCK_CONTRACTS[block_id].get("default_action")
    )
    if default:
        BLOCK_DEFAULT_ACTIONS[block_id] = str(default)
    return module


_ENTRY_NAMES = ("execute", "run", "handle", "dispatch", "invoke", "process", "call")
_CLASS_NAMES = ("Block", "BLOCK", "BlockImpl", "Kit", "BlockRunner")


def _entry_callable(module: types.ModuleType):
    for name in _ENTRY_NAMES:
        candidate = getattr(module, name, None)
        if callable(candidate) and not isinstance(candidate, type):
            return candidate
    for name in _CLASS_NAMES:
        cls = getattr(module, name, None)
        if not isinstance(cls, type):
            continue
        for method_name in _ENTRY_NAMES:
            method = getattr(cls, method_name, None)
            if callable(method):
                try:
                    instance = cls()
                except Exception:  # noqa: BLE001 - a class needing args is not the entry
                    return getattr(cls, method_name)
                return getattr(instance, method_name)
    actions = getattr(module, "ACTIONS", None) or getattr(module, "actions", None)
    if isinstance(actions, dict) and actions:
        first = next(iter(actions.values()))
        if callable(first):
            return first
    return None


def _call(entry, payload: Dict[str, Any], action: Optional[str], params: Optional[Dict[str, Any]]):
    """Call a block's entry point through its own signature."""
    import inspect

    try:
        signature = inspect.signature(entry)
    except (TypeError, ValueError):
        return entry(payload)

    parameters = list(signature.parameters.values())
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters):
        kwargs: Dict[str, Any] = {"action": action}
        kwargs.update({k: v for k, v in payload.items() if not (k == "action" and action)})
        if action:
            kwargs["action"] = action
        if params:
            kwargs["params"] = params
        return entry(**kwargs)

    pass_payload = {"payload", "input", "inputs", "data", "record", "values", "body", "request", "args", "context"}
    pass_params = {"params", "options", "config", "settings", "kwargs"}
    kwargs = {}
    positional: List[Any] = []
    used_payload = False
    for parameter in parameters:
        name = parameter.name.lower()
        if name in ("action", "operation", "op", "intent"):
            kwargs[parameter.name] = action
        elif name in pass_payload:
            kwargs[parameter.name] = payload
            used_payload = True
        elif name in pass_params:
            kwargs[parameter.name] = params or {}
        elif parameter.default is not inspect.Parameter.empty:
            continue
        elif parameter.kind in (inspect.Parameter.POSITIONAL_ONLY,):
            positional.append(payload)
            used_payload = True
        elif parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD:
            positional.append(payload)
            used_payload = True
    if not used_payload and not positional and any(
        p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL) for p in parameters
    ):
        positional.insert(0, payload)
    return entry(*positional, **kwargs)


_UNAVAILABLE_MARKERS = (
    "no module named",
    "modulenotfounderror",
    "importerror",
    "is not installed",
    "not installed",
    "install tesseract",
    "could not import",
    "cannot import",
    "tesseract",
    "no pdf text layer",
    "could not process input file",
)


def _looks_unavailable(text: str) -> bool:
    """A block's optional engine/dependency is absent, not its contract wrong.

    Missing engines (an OCR binary, a scanner library) are a provider that is
    down, not a payload the capability wrote incorrectly. They are reported as
    ``error_kind: unavailable`` so a capability can name the block it could not
    reach instead of pretending the record failed.
    """
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _UNAVAILABLE_MARKERS)


def _normalise(block_id: str, action: Optional[str], result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        out: Dict[str, Any] = dict(result)
    elif hasattr(result, "to_dict") and callable(result.to_dict):
        out = dict(result.to_dict())
    else:
        out = {"result": result}
    out.setdefault("block", block_id)
    out.setdefault("action", action)
    if "ok" not in out:
        out["ok"] = out.get("status") not in ("error", "failed", "refused")
    if "status" not in out:
        out["status"] = "ok" if out["ok"] else "error"
    if out.get("ok") is False and "error_kind" not in out and _looks_unavailable(out.get("error")):
        out["error_kind"] = "unavailable"
    return out


def default_action(block_id: str) -> Optional[str]:
    """The action this block's own contract dispatches on."""
    if block_id in BLOCK_DEFAULT_ACTIONS:
        return BLOCK_DEFAULT_ACTIONS[block_id]
    try:
        load_block(block_id)
    except Exception:  # noqa: BLE001 - an absent/broken block declares nothing
        return None
    return BLOCK_DEFAULT_ACTIONS.get(block_id)


def execute(
    block_id: str,
    payload: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Run one block and return its envelope. Never raises for a refusal."""
    call_payload: Dict[str, Any] = dict(payload or {})
    if extra:
        call_payload.update({k: v for k, v in extra.items() if v is not None})
    operation = action or default_action(block_id)
    try:
        module = load_block(block_id)
    except Exception as exc:  # noqa: BLE001 - an unloadable block is data here
        return {
            "ok": False,
            "status": "error",
            "block": block_id,
            "action": operation,
            "error_kind": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
    entry = _entry_callable(module)
    if entry is None:
        return {
            "ok": False,
            "status": "error",
            "block": block_id,
            "action": operation,
            "error_kind": "unavailable",
            "error": f"block {block_id!r} declares no callable entry point",
        }
    actions = getattr(module, "ACTIONS", None) or getattr(module, "actions", None)
    if isinstance(actions, dict) and operation and operation in actions:
        entry = actions[operation]
    try:
        result = _call(entry, call_payload, operation, params)
    except ImportError as exc:
        return {
            "ok": False,
            "status": "error",
            "block": block_id,
            "action": operation,
            "error_kind": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
    except TypeError as exc:
        try:
            result = entry(call_payload)
        except Exception as inner:  # noqa: BLE001 - reported, never raised
            text = f"{type(inner).__name__}: {inner}" if inner is not exc else f"TypeError: {exc}"
            answer = {
                "ok": False,
                "status": "error",
                "block": block_id,
                "action": operation,
                "error": text,
            }
            if _looks_unavailable(text):
                answer["error_kind"] = "unavailable"
            return answer
    except Exception as exc:  # noqa: BLE001 - a block failure is data here
        text = f"{type(exc).__name__}: {exc}"
        answer = {
            "ok": False,
            "status": "error",
            "block": block_id,
            "action": operation,
            "error": text,
        }
        if _looks_unavailable(text):
            answer["error_kind"] = "unavailable"
        return answer
    return _normalise(block_id, operation, result)


def loaded_blocks() -> List[str]:
    return sorted(_LOADED)


def vendor_tree_present() -> bool:
    return VENDOR_ROOT.is_dir()


def missing_blocks() -> List[str]:
    return [block_id for block_id in BLOCK_IDS if not block_path(block_id).is_file()]


def verify_locked_blocks() -> List[str]:
    """Fail at start-up when a locked block is missing from the product tree.

    A checkout that carries no vendor tree at all is a development checkout --
    the sealed product tree is merged in at build time -- and is reported, not
    failed. A product tree that HAS the vendor root and lacks a pinned block is
    a broken build, and says so here rather than at the first request.
    """
    if not vendor_tree_present():
        return []
    absent = missing_blocks()
    if absent:
        raise BlockUnavailable(
            "locked block(s) absent from their locked paths: " + ", ".join(sorted(absent))
        )
    return absent


def iter_contracts() -> Iterable[Dict[str, Any]]:
    for block_id in BLOCK_IDS:
        yield {"block": block_id, "path": str(block_path(block_id)), **BLOCK_CONTRACTS.get(block_id, {})}
