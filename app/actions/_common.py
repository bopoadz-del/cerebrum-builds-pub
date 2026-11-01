"""Shared helpers for this platform's capability handlers.

Written by the factory WRITER role (codewhale exec).

Nothing in here names a capability or a block: each handler owns its own
domain decision, its own block inputs and its own refusals. What lives here
is the small amount of arithmetic and reading that every handler does the
same way -- normalising a caller's record against the capability's declared
fields, reading a customer-owned threshold from a named setting, and
noticing a failure a block reported one level down (a delivery whose tool
call failed, a pipeline step that errored) so a capability never reports
success around a failed child.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Sequence

#: Statuses a nested result uses to say it did not succeed.
_FAILED = ("error", "failed", "partial")


def record_of(capability_id: str, payload: Any) -> Dict[str, Any]:
    """The caller's payload as the capability's own declared record.

    Every declared field is present in the answer (missing and null become
    an empty string, or 0/0.0 for the numeric fields) so a handler never has
    to branch on presence, and a key the capability does not declare is
    dropped rather than carried into a block call as unknown input.
    """
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    data = dict(payload) if isinstance(payload, dict) else {}
    if cls is None:
        return data
    out: Dict[str, Any] = {}
    for name in getattr(cls, "FIELDS", []) or []:
        value = data.get(name)
        if value is None:
            value = ""
        out[name] = value
    return out


def text_of(name: str, value: Any) -> str:
    """One field as the text a block can read."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def number_of(value: Any, default: float = 0.0) -> float:
    """One field as a number, without inventing a value it did not carry."""
    if isinstance(value, bool) or value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def whole_of(value: Any, default: int = 0) -> int:
    try:
        return int(number_of(value, float(default)))
    except (TypeError, ValueError):
        return default


def setting(name: str, default: str) -> str:
    """A customer-owned setting: the operator's value, else the shipped
    default. Every name used here is listed in README.md, so the factory can
    change the threshold without a code change."""
    return (os.environ.get(name) or "").strip() or str(default)


def setting_number(name: str, default: float) -> float:
    return number_of(setting(name, str(default)), float(default))


def summary_of(record: Dict[str, Any], keys: Sequence[str]) -> str:
    """A one-line, block-safe summary of a record: only its own values."""
    parts = [
        "%s=%s" % (key, record.get(key))
        for key in keys
        if record.get(key) not in (None, "", 0, 0.0, False)
    ]
    return "; ".join(parts)[:500] or "record"


def text_input(record: Dict[str, Any], heading: str, keys: Sequence[str]) -> str:
    """The record as the text a document/text block reads.

    A block that analyses prose is handed prose built from the caller's own
    values, never a paragraph this module invented: the heading names the
    capability's subject and each key is one of the record's own fields.
    """
    lines = [heading]
    for key in keys:
        value = record.get(key)
        if value in (None, "", 0, 0.0, False):
            continue
        lines.append("%s: %s" % (key.replace("_", " "), value))
    return "\n".join(lines)[:4000]


def nested_refusals(block_id: str, answer: Any) -> List[str]:
    """Failures a block reported *inside* its own success envelope.

    Two shapes are real in the Store, and both were measured on a booted
    build: the workflow block answers ``status: success`` while one of its
    steps came back ``status: failed``, and the notification block answers
    ``status: success, sent: true`` while the tool call it made through the
    mcp channel returned an error (carried in ``result_preview`` as JSON).
    A capability that reported success around either would be lying about
    work it did not do, so both are named here and become the capability's
    refusal.
    """
    out: List[str] = []
    if not isinstance(answer, dict):
        return out
    for step in (answer.get("results") or []):
        if isinstance(step, dict) and str(step.get("status") or "").lower() in _FAILED:
            out.append(
                "%s: step %s (%s): %s"
                % (
                    block_id,
                    step.get("step_id") or "?",
                    step.get("block") or "?",
                    str(step.get("error") or step.get("status"))[:160],
                )
            )
    preview = answer.get("result_preview")
    if isinstance(preview, str) and preview.strip().startswith("{"):
        try:
            inner = json.loads(preview)
        except ValueError:
            inner = None
        if isinstance(inner, dict):
            if inner.get("ok") is False or str(inner.get("status") or "").lower() in _FAILED:
                detail = inner.get("error")
                if not detail:
                    result = inner.get("result")
                    if isinstance(result, dict):
                        detail = result.get("error") or result.get("status")
                out.append("%s: delivered tool call refused: %s" % (block_id, str(detail)[:160]))
    return out


def authority(capability_id: str, layer: int, name: str) -> Dict[str, Any]:
    """The layer of precedence.v1 this capability's answer came from.

    Layer 1 certified > 2 documents > 3 formulas > 4 procedures: a handler
    that answers from the factory's own arithmetic answers at the formulas
    layer, one that answers from an extracted document answers at the
    documents layer, and the principal roster (a certified decision list)
    answers at layer 1. The label travels with the answer so an operator can
    see which layer it came from.
    """
    return {
        "layer": int(layer),
        "name": str(name),
        "source": "app/actions/%s.py" % capability_id,
    }


def refusal(capability_id: str, label: Dict[str, Any], refusals: Sequence[str],
            answers: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    """A capability's refusal: ok is false, the refusing block is named, and
    nothing was persisted (the route only saves an ok answer)."""
    body: Dict[str, Any] = {
        "ok": False,
        "capability": capability_id,
        "error": "; ".join(str(item) for item in refusals)[:600],
        "blocks": answers,
        "authority": dict(label),
    }
    body.update(extra)
    return body


def success(capability_id: str, label: Dict[str, Any], answers: Dict[str, Any],
            **extra: Any) -> Dict[str, Any]:
    """A capability's answer: ok is true, its own decision in ``result``, and
    every block answer kept beside it."""
    body: Dict[str, Any] = {
        "ok": True,
        "capability": capability_id,
        "blocks": answers,
        "authority": dict(label),
    }
    body.update(extra)
    return body


def declared_action(block_id: str, name: str) -> str:
    """The action ``name`` if the block's OWN contract declares it, else "".

    A handler that needs a block's other declared operation (the record
    surface's ``create_table`` before its ``insert``) reads the name out of
    the harvested contract rather than typing it from memory or from another
    product: an action no block declares is not sent, and the handler says
    so instead of guessing.
    """
    from app.block_contracts import BLOCK_CONTRACTS

    contract = BLOCK_CONTRACTS.get(str(block_id)) or {}
    declared = {str(item) for item in (contract.get("action_options") or [])}
    default = contract.get("default_action")
    if isinstance(default, str):
        declared.add(default)
    wanted = str(name or "").strip()
    return wanted if wanted in declared else ""


def declared_refusal_prefix(block_id: str, word: str) -> str:
    """The literal prefix of a block's own declared refusal, else "".

    A block's contract carries the errors its code states ("duplicate record
    id: {record['id']}" for the estate register). When a refusal is an
    EXPECTED, idempotent outcome -- registering a collection task that is
    already listed -- the handler recognises it by the block's own words rather
    than by a phrase typed here, and the placeholder is cut off so only the
    literal prefix is matched.
    """
    from app.block_contracts import BLOCK_CONTRACTS

    contract = BLOCK_CONTRACTS.get(str(block_id)) or {}
    wanted = str(word or "").strip().lower()
    for text in contract.get("runtime_error_contracts") or []:
        literal = str(text)
        if not literal.lower().startswith(wanted):
            continue
        for marker in ("{", "("):
            cut = literal.find(marker)
            if cut > 0:
                literal = literal[:cut]
        return literal.strip()
    return ""
