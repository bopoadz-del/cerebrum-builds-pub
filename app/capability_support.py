"""Shared plumbing for the capabilities: identity, block runs, envelopes.

Deliberately not a handler: it carries no domain decision. It exists so every
capability runs its declared blocks through the SAME fail-closed path -- each
block's own default action, a constructed input, and a refusal propagated as
``ok: false`` with nothing stored.

READS   the request record and app.block_inputs.
WRITES  capability artifacts under STORAGE_PATH/workspace via workspace_dir().
NEVER   persists a record -- the route owns the tenant-scoped save.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from app import block_inputs
from app.block_inputs import default_block_action
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute

AUTHORED_BY = "codewhale exec"


def workspace_dir(capability_id: str) -> Path:
    """Where a capability may write its artifacts (inside the one root)."""
    from app import store

    path = store.storage_root() / "workspace" / capability_id
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # A read-only root must not turn a domain answer into an exception;
        # the artifact is evidence, not the decision.
        pass
    return path


def artifact_name(prefix: str, content: Any, suffix: str = "json") -> str:
    """A content-addressed artifact name: same evidence, same name."""
    return f"{prefix}_{digest(content)[:12]}.{suffix}"


def write_artifact(directory: Path, name: str, body: Any) -> str:
    """Write evidence beside the record, tolerating a read-only root."""
    path = directory / name
    try:
        path.write_text(
            body if isinstance(body, str) else json.dumps(body, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return str(path)
    return str(path)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def run_blocks(
    capability_id: str,
    record: Dict[str, Any],
    block_ids: Iterable[str],
    inputs: Optional[Dict[str, Dict[str, Any]]] = None,
    run: Any = None,
    actions: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Optional[str], list]:
    """Execute every declared block; stop at the first real refusal.

    Returns (answers by block id, refusal text or None, unavailable block ids).
    A block whose optional engine/dependency is absent is named, not treated as
    a contract failure -- the capability still does its own deterministic work.
    """
    runner = run or execute
    answers: Dict[str, Any] = {}
    unavailable: list = []
    overrides = inputs or {}
    chosen_actions = actions or {}
    chosen_params = params or {}
    for block_id in block_ids:
        action = (
            chosen_actions.get(block_id)
            or BLOCK_DEFAULT_ACTIONS.get(block_id)
            or default_block_action(block_id)
        )
        payload = overrides.get(block_id)
        if payload is None:
            payload = block_inputs.prepare_block_input(
                block_id, record, capability_id=capability_id
            )
        else:
            payload = dict(payload)
            if block_id == "notification":
                payload.setdefault("topic", block_inputs.event_topic(record, capability_id))
                payload.setdefault("message", block_inputs.event_message(record, capability_id))
                payload.setdefault("channel", block_inputs.MCP_CHANNEL)
        block_params = chosen_params.get(block_id)
        if block_params is not None:
            answer = runner(block_id, payload, action=action, params=dict(block_params))
        else:
            answer = runner(block_id, payload, action=action)
        answers[block_id] = answer
        if isinstance(answer, dict) and answer.get("error_kind") == "unavailable":
            unavailable.append(block_id)
            continue
        refusal = block_inputs.failure(answer)
        if refusal:
            return answers, f"{block_id}: {refusal}", unavailable
    return answers, None, unavailable


def input_digest(record: Dict[str, Any]) -> str:
    """A deterministic fingerprint of exactly what the caller sent.

    Every answer carries it, so two different requests are distinguishable
    even when they produce the same decision, and two identical requests are
    not -- the answer never varies with a clock or a random value that the
    request did not carry.
    """
    clean = {
        str(key): value
        for key, value in (record or {}).items()
        if not str(key).startswith("_")
    }
    return digest(clean)


def ok(capability_id: str, result: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    payload = {
        "ok": True,
        "capability_id": capability_id,
        "result": result,
        "authority": result.get("authority") or "layer 3 formulas",
    }
    payload.update(extra)
    return payload


def refuse(error: str, error_kind: str = "refused", **extra: Any) -> Dict[str, Any]:
    payload = {"ok": False, "error": error, "error_kind": error_kind}
    payload.update(extra)
    return payload


def text_of(record: Dict[str, Any], *names: str) -> str:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def number_of(record: Dict[str, Any], name: str, default: float = 0.0) -> float:
    value = record.get(name)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def int_of(record: Dict[str, Any], name: str, default: int = 0) -> int:
    value = number_of(record, name, float(default))
    return int(value)


def as_date(value: Any, default: Optional[date] = None) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return default


def round_money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def reference_of(record: Dict[str, Any]) -> str:
    return text_of(record, "reference") or "unreferenced"


def stamp(record: Dict[str, Any]) -> str:
    return digest({k: v for k, v in (record or {}).items() if not str(k).startswith("_")})
