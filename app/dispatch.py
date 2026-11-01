"""Local block dispatch. No network, no store, no callback.

The old generated platforms answered a capability by POSTing to the operator's
block store. This imports the block that was vendored into this repository at
build time and calls it in-process, which is what makes the platform runnable
offline and independent of the factory's uptime.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict


def _vendor_root() -> Path:
    """Where the sealed vendored blocks live.

    The delivered product carries ``vendor/blocks`` itself. A staged writer
    checkout (``.<name>.staging-writer``) carries no vendor slice of its own;
    the Factory has already assembled it beside the staging tree, so the
    sibling destination's sealed copy is used -- the same blocks the built
    image will run.
    """
    import os

    override = str(os.environ.get("BLOCKS_VENDOR_PATH") or "").strip()
    if override:
        return Path(override)
    repo = Path(__file__).resolve().parents[1]
    local = repo / "vendor" / "blocks"
    if local.is_dir():
        return local
    suffix = ".staging-writer"
    if repo.name.startswith(".") and repo.name.endswith(suffix):
        sibling = repo.parent / repo.name[1 : -len(suffix)] / "vendor" / "blocks"
        if sibling.is_dir():
            return sibling
    return local


_VENDOR = _vendor_root()
_CACHE: Dict[str, Any] = {}


def _ensure_vendor_importable() -> None:
    """The vendored adapters import their runtime as ``vendor.cerebrum...``."""
    root = str(_VENDOR.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


class BlockNotVendored(RuntimeError):
    """Asked for a block this platform does not carry."""


def load_block(block_id: str):
    """The vendored block for this id, else the platform's offline fallback.

    A vendored block is the real Store method and always wins.  A block this
    platform carries as a local offline shim (app/local_blocks/<id>.py) is
    resolved from there rather than refused, so a capability's declared block
    call answers offline; a block that is neither is not silently accepted --
    BlockNotVendored is raised and the capability fails closed on it.
    """
    if block_id in _CACHE:
        return _CACHE[block_id]
    _ensure_vendor_importable()
    path = _VENDOR / block_id / "block.py"
    if path.is_file():
        spec = importlib.util.spec_from_file_location(f"vendored_{block_id}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CACHE[block_id] = module
        return module
    try:
        import importlib as _importlib

        module = _importlib.import_module("app.local_blocks." + str(block_id))
    except Exception as exc:  # noqa: BLE001 - the miss is the diagnosis
        raise BlockNotVendored(
            f"{block_id} is not vendored in this platform (looked in {path}) "
            f"and has no local offline fallback: {type(exc).__name__}: {exc}"
        )
    _CACHE[block_id] = module
    return module


from app.block_contracts import BLOCK_CONTRACTS



class DispatchContractError(ValueError):
    """Caller payload failed the harvested contract. Do not invent fields."""


#: Every envelope this dispatcher had to normalise, as
#: ``(block_id, lifted_keys)``. A silent normalisation is still a defect in
#: the generated handler; the WRITER contract probe reads this list so the
#: mismatch is NAMED rather than absorbed.
_LIFTED: list = []


def _required_fields(block_id: str) -> list:
    contract = BLOCK_CONTRACTS.get(block_id) or {}
    required = list(contract.get("input_required_fields") or [])
    for item in contract.get("declared_inputs") or []:
        name = item.get("name") if isinstance(item, dict) else None
        if name and item.get("required") and name not in required:
            required.append(name)
    return [field for field in required if field != "action"]


def _known_fields(block_id: str) -> set:
    """Closed field set from the harvested contract. Empty = no allow-list.

    Three sources, and the third is the one that was missing:

    * ``declared_inputs`` -- the block's CONFIG parameters, from block.json
      (backend, connection_string, theme, ...).
    * ``input_required_fields`` -- what the block refuses to run without.
    * ``input_keys_read_by_block`` -- the keys the block's own code actually
      reads off its payload at run time (table, values, where, file_path,
      user_id, ...). WORKAROUND, harvested from source; see
      CerebrumDev.ai#256 and Cerebrum-Blocks#90.

    Leaving the third one out is what made every generated platform inert.
    ``database`` declares only {input, backend, connection_string}, so a
    correct call -- ``{"table": "crew_logs", "values": {...}}`` -- had both
    keys counted as stray, folded into ``input`` by _adapt_input below, and
    handed to the block double-wrapped. ``_insert`` then read ``table=None``
    and ``values={}`` and emitted ``INSERT INTO None () VALUES ()``:

        database: Insert failed: near ")": syntax error

    One defect, four faces, measured on the booted zip of session
    Live: ``document_engine`` answered "No input files provided"
    holding a file_path, ``notification`` answered "block or tool name
    required for MCP channel" holding a block name, and ``team`` answered
    "Team access denied" holding a user_id. The platform built, shipped,
    booted and served all seventeen routes -- and could not persist a row.

    The fold itself stays: a key the block never reads is still a domain
    record and still belongs in ``input`` (the warehouse `audit` case the
    fold was written for). Only keys the block reads stay flat.
    """
    contract = BLOCK_CONTRACTS.get(block_id) or {}
    names: set = set()
    for item in contract.get("declared_inputs") or []:
        name = item.get("name") if isinstance(item, dict) else None
        if name and name != "action":
            names.add(name)
    for field in contract.get("input_required_fields") or []:
        if field != "action":
            names.add(field)
    keys_read = contract.get("input_keys_read_by_block") or []
    for field in keys_read:
        if field and field != "action":
            names.add(str(field))
    # A block whose own code reads the operation off its PAYLOAD (rather than
    # off the dispatch params) declares that in the harvested contract: the
    # operation key is then a field the block reads, so the resolved action
    # travels with the record as well as in the action= keyword. Without this
    # the block answers "unknown action: (none)" holding an action it cannot
    # see -- measured on approval_rules, whose every other action also needs
    # a payload the payload-action block reads.
    if "action" in keys_read:
        names.add("action")
    return names


def _keys_read(block_id: str) -> set:
    """Only the keys the block's CODE reads off its payload at run time.

    Distinct from ``_known_fields``, which also carries block.json's declared
    CONFIG params. The distinction is what tells a declared ``input`` slot
    from one the block actually reads: measured on the vendored blocks,
    ``analytics``, ``database``, ``team`` and ``storage`` contain ZERO
    ``.get("input")`` -- they read their keys flat -- while ``workflow``
    reads one. Both facts are needed below.

    WORKAROUND: ``input_keys_read_by_block`` is regex-harvested from the
    vendored source because no manifest declares it yet. When block.json
    carries ``requires_inputs`` (Cerebrum-Blocks#90), that declaration
    replaces this read -- removal tracked in CerebrumDev.ai#256.
    """
    contract = BLOCK_CONTRACTS.get(block_id) or {}
    return {
        str(f) for f in (contract.get("input_keys_read_by_block") or []) if f
    }


def _envelope_mismatch(block_id: str, data: Dict[str, Any]) -> tuple:
    """Is the caller's record one level too deep for this block?

    Returns ``(buried, colliding)`` -- the keys the block reads that sit
    inside ``data["input"]`` instead of at the top level, and any of those
    that already exist at the top level with a different value.

    THE INCIDENT (post-#254).
    ``unit_registry_and_vacancy_tracking`` called::

        execute("analytics", {"input": {"metric": "monthly_rent_gbp",
                                        "value": 1450.0, ...}},
                action="track_event")

    and got ``{'error': 'metric and value required'}``. Verified literally in
    the block source: ``AnalyticsBlock._track_event`` reads
    ``data.get("metric")`` and ``data.get("value")`` off the payload it is
    handed, and ``analytics``' block.json declares ``input`` only as a config
    slot -- the code never reads it. Both fields were present in the spec, so
    a plan-time audit that looks for NAMES passes; the block still saw
    neither. That is #254's class one level deeper, and the same file wrapped
    three different shapes with no rule.
    """
    reads = _keys_read(block_id)
    if not reads or "input" in reads:
        # The block genuinely reads an ``input`` key (``workflow`` does).
        # Its wrapper is the contract, not a mistake.
        return (), ()
    inner = data.get("input")
    if not isinstance(inner, dict):
        return (), ()
    buried = sorted(k for k in inner if k in reads and k != "action")
    colliding = sorted(
        k for k in buried if k in data and data[k] != inner[k]
    )
    return tuple(buried), tuple(colliding)


def _adapt_input(block_id: str, payload: Any, action: str | None) -> Dict[str, Any]:
    """Pass the caller payload through. Never invent Store fields (F18).

    A MISMATCHED ENVELOPE IS NEVER PASSED THROUGH SILENTLY. Either the
    record is normalised to the shape the block reads, or the call fails
    with the mismatch named -- it does not reach the block wearing a shape
    the block cannot read (owner's ruling R1d, 2026-09-01).
    """
    data = dict(payload) if isinstance(payload, dict) else {"value": payload}
    known = _known_fields(block_id)

    buried, colliding = _envelope_mismatch(block_id, data)
    if colliding:
        # Two different values for the same field, one nested and one flat.
        # Normalising would have to choose, and choosing is inventing.
        verb = "appears" if len(colliding) == 1 else "appear"
        raise DispatchContractError(
            f"{block_id} envelope mismatch: {', '.join(colliding)} {verb} both "
            f"at the top level and inside 'input' with different values; "
            f"{block_id} reads them at the top level. Pass the record flat."
        )
    if buried:
        inner = dict(data.get("input") or {})
        for key in buried:
            data[key] = inner.pop(key)
        if inner:
            data["input"] = inner
        else:
            data.pop("input", None)
        _LIFTED.append((block_id, tuple(buried)))
    # Store blocks are action-dispatched: the domain record travels in the
    # block's declared ``input`` slot, with block params beside it. A handler
    # that passes the record flat gets every domain key refused as unknown --
    # measured on the warehouse `audit` capability, which declares
    # reference/status/quantity in its own model and had all three rejected.
    #
    # This is adaptation, not F18 fabrication. No value is invented and no
    # field is conjured to satisfy a validator: the caller's own record is
    # placed in the field the block declares for exactly it. If the caller
    # already supplied ``input``, nothing is moved.
    if known and "input" in known and "input" not in data:
        stray = {k: v for k, v in data.items() if k not in known}
        if stray:
            data = {k: v for k, v in data.items() if k in known}
            data["input"] = stray
    missing = [
        field for field in _required_fields(block_id)
        if field not in data or data[field] in (None, "")
    ]
    if missing:
        raise DispatchContractError(
            f"{block_id} missing required field(s): {', '.join(missing)}"
        )
    if known:
        unknown = sorted(str(key) for key in data if key not in known)
        if unknown:
            raise DispatchContractError(
                f"{block_id} unknown field(s): {', '.join(unknown)}"
            )
    return data


#: A block that answers with one of these has NOT succeeded. "partial" is the
#: word both the workflow and notification blocks use for "some of it failed"
#: -- workflow sets it on every step that raises, times out, names an unknown
#: block, or returns an error. Reading only "error" let a pipeline whose only
#: step failed come back as success.
_FAILED_STATUSES = {"error", "failed", "partial"}


def _failed_steps(result: Dict[str, Any]) -> list:
    """Sub-step failures the top-level status may not carry.

    Live, from a booted build: a capability returned
    ``ok: true`` wrapped around

        {"status": "partial", "results": [{"step_id": "step_0",
          "block": "database", "status": "failed",
          "error": "DatabaseBlock.__init__() missing 2 required positional
          arguments: 'hal_block' and 'config'"}]}

    The capability reported success. The row was never written.
    """
    steps = result.get("results")
    if not isinstance(steps, list):
        steps = result.get("steps")
    if not isinstance(steps, list):
        return []
    return [
        step for step in steps
        if isinstance(step, dict)
        and str(step.get("status") or "").lower() in {"error", "failed"}
    ]


def _error_envelope(block_id: str, action: str | None, error: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "block": block_id,
        "action": action,
        "error": error,
        "ok": False,
    }


_ENV_READS: Any = None


def _is_environ(node: Any) -> bool:
    import ast

    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return isinstance(node, ast.Name) and node.id == "environ"


def _vendored_env_reads() -> set:
    """Every setting name the vendored source reads from the environment.

    Read off the vendored bytes, once: no manifest declares required env, so
    the source is the only honest record of what a block needs configured.
    """
    global _ENV_READS
    if _ENV_READS is not None:
        return _ENV_READS
    import ast

    names = set()
    for path in _VENDOR.parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(tree):
            key = None
            if isinstance(node, ast.Subscript) and _is_environ(node.value):
                key = node.slice
            elif isinstance(node, ast.Call) and node.args:
                fn = node.func
                if isinstance(fn, ast.Attribute) and (
                    (fn.attr in ("get", "pop") and _is_environ(fn.value))
                    or (
                        fn.attr == "getenv"
                        and isinstance(fn.value, ast.Name)
                        and fn.value.id == "os"
                    )
                ):
                    key = node.args[0]
                elif isinstance(fn, ast.Name) and fn.id == "getenv":
                    key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                names.add(key.value)
    _ENV_READS = names
    return names


def unavailable_reason(block_id: str, error: Any) -> str | None:
    """Why a block failure is really "credentials not configured", or None.

    A connector with no credentials is a DECLARED STUB, not a failure: the
    DevOps team supplies them at deploy. Recognised when the block's own
    refusal names a setting the vendored source reads from the environment
    AND that setting is unset here. No block and no setting is named in this
    file -- both come from the vendored source and the block's own words.
    """
    import os
    import re

    text = str(error or "")
    if not text:
        return None
    missing = sorted(
        name
        for name in _vendored_env_reads()
        if not str(os.environ.get(name) or "").strip()
        and re.search("(?<![A-Za-z0-9_])" + re.escape(name) + "(?![A-Za-z0-9_])", text)
    )
    if missing:
        return "credentials not configured: " + ", ".join(missing)
    # A connector whose optional runtime is not installed (the offline
    # platform ships only its declared runtime requirements, so a block's
    # own optional client library may be absent) is the same class of answer
    # as an unset credential: the connector is not configured on this host,
    # and the capability's own record work continues without it. Named from
    # the block's own error, never guessed: the import the block could not
    # perform is the evidence.
    absent = re.search(r"No module named '([A-Za-z0-9_.]+)'", text)
    if absent:
        return "optional runtime not installed: " + absent.group(1)
    # A block that states its own install line is stating the same fact in
    # the other direction: the optional runtime is not on this host. The
    # name comes from the block's own words (marker: "no PDF engine
    # installed (tried pypdfium2, pymupdf). Install it with: pip install
    # pypdfium2"), never from a list kept here.
    hint = re.search(r"pip install\s+([A-Za-z0-9_.\-]+)", text)
    if hint:
        return "optional runtime not installed: " + hint.group(1).rstrip(".")
    return None


def _declared_stub(block_id: str, action: str | None, reason: str) -> Dict[str, Any]:
    """SUCCESS envelope for a connector whose credentials are not configured."""
    return {
        "status": "success",
        "ok": True,
        "block": block_id,
        "action": action,
        "stub": True,
        "result": {"stub": True},
        "blocks_unavailable": [block_id],
        "reason": reason,
    }


def _force_utf8_stdio() -> None:
    """F13: a checkmark/emoji print must not become a charmap crash.

    Windows cp1252 consoles encode print() with the console codepage. A
    vendored block that prints one checkmark used to raise UnicodeEncodeError;
    execute() then swallowed that into a generic error envelope that looked
    like a domain refusal. Force UTF-8 on this process before the block runs.
    """
    import os
    import sys

    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            continue


_force_utf8_stdio()


def execute(
    block_id: str,
    payload: Dict[str, Any],
    action: str | None = None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run a vendored block locally and return its result envelope.

    Real Store blocks are action-dispatched: the domain data travels as
    ``input`` and the operation name as ``action`` (each block declares a
    default in its block.json). A call with no action reaches blocks that
    answer "Unknown action" -- pass the one the capability needs.

    Missing required fields and unknown fields/params become an error
    envelope. A block refusal (status=error) is returned as-is — never
    rewritten to ok.
    """
    module = load_block(block_id)
    run = getattr(module, "run", None)
    if run is None:
        raise BlockNotVendored(f"{block_id} exposes no run() entry point")
    contract = BLOCK_CONTRACTS.get(block_id) or {}
    declared = set()
    for item in contract.get("declared_inputs") or []:
        name = item.get("name") if isinstance(item, dict) else None
        if name:
            declared.add(name)
    if (
        params
        and (contract.get("declared_inputs") or contract.get("input_required_fields"))
    ):
        extra = sorted(
            str(key) for key in params if key not in declared and key != "action"
        )
        if extra:
            return _error_envelope(
                block_id, action, f"unknown param(s): {', '.join(extra)}"
            )
    kwargs = dict(params or {})
    if action is not None:
        kwargs["action"] = action
    try:
        adapted = _adapt_input(block_id, payload, action)
    except DispatchContractError as exc:
        return _error_envelope(block_id, action, str(exc))
    if action is not None and "action" in _keys_read(block_id):
        # The block reads the operation from the payload: carry the resolved
        # action in with the record. The keyword is still passed; a block that
        # prefers params.get("action") keeps winning.
        adapted.setdefault("action", action)
    # A block-level failure comes back as data, not as an exception. The
    # Store's shim raises RuntimeError on an error envelope, which destroys
    # the diagnosis: a handler (and a failing test) sees "Input validation
    # failed" with no block name and no field list. Structural failures --
    # a block that is not vendored -- still raise above.
    _force_utf8_stdio()
    try:
        result = run(input=adapted, **kwargs)
    except BlockNotVendored:
        raise
    except UnicodeEncodeError as exc:
        return _error_envelope(
            block_id,
            action,
            f"UnicodeEncodeError on block stdout (encoding, not domain): {exc}",
        )
    except Exception as exc:
        reason = unavailable_reason(block_id, exc)
        if reason:
            return _declared_stub(block_id, action, reason)
        return _error_envelope(
            block_id, action, f"{type(exc).__name__}: {exc}"
        )
    if isinstance(result, dict):
        status = str(result.get("status") or "").lower()
        failed = _failed_steps(result)
        if status in _FAILED_STATUSES or result.get("ok") is False or failed:
            reason = unavailable_reason(
                block_id, result.get("error") or result.get("message") or ""
            )
            if reason:
                return _declared_stub(block_id, action, reason)
            refused = dict(result)
            refused["status"] = status if status in _FAILED_STATUSES else "error"
            refused.setdefault("block", block_id)
            refused["ok"] = False
            if failed and not refused.get("error"):
                refused["error"] = "; ".join(
                    "%s (%s): %s" % (
                        step.get("step_id") or "step",
                        step.get("block") or "?",
                        str(step.get("error") or step.get("status"))[:160],
                    )
                    for step in failed
                )
            return refused
    return result
