"""Shared helpers for the the project capability handlers.

Nothing here names a capability or makes a domain decision: each handler
owns its arithmetic, its block inputs and its refusals. What lives here is
the repeated small work -- normalising a caller's record against the
capability's declared fields, reading a customer-owned threshold, naming the
authority layer, and noticing a failure a block reported one level down.

Scope (every handler importing this module)
READS   the caller's payload, app/sources.py, app/formulas.py, app.money_settings,
        the vendored blocks.
WRITES  caller output only -- the HTTP route owns persistence.
NEVER   no network, no currency or rate the operator did not declare, no
        invented document or BOQ line.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Sequence

from app import formulas, money_settings, sources

_FAILED = ("error", "failed", "partial")


def record_of(capability_id: str, payload: Any) -> Dict[str, Any]:
    """The caller's payload restricted to the capability's declared fields."""
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    data = dict(payload) if isinstance(payload, dict) else {}
    if cls is None:
        return data
    out: Dict[str, Any] = {}
    for name in getattr(cls, "FIELDS", []) or []:
        value = data.get(name)
        if value is None:
            kind = (getattr(cls, "CONSTRAINTS", {}) or {}).get(name, {}).get("type")
            value = False if kind == "bool" else 0 if kind == "int" else 0.0 if kind == "float" else ""
        out[name] = value
    out["_input_digest"] = submission_digest(data)
    return out


def submission_digest(payload: Any) -> str:
    canonical = json.dumps(
        payload if isinstance(payload, dict) else {"value": payload},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def number_of(value: Any, default: float = 0.0) -> float:
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


def money_round(value: Any) -> float:
    return round(number_of(value), 2)


def setting(name: str, default: str) -> str:
    return (os.environ.get(name) or "").strip() or str(default)


def setting_number(name: str, default: float) -> float:
    return number_of(setting(name, str(default)), float(default))


_BOQ_CURRENCY = re.compile(r"rate\s*\(([A-Za-z]{3})\)", re.IGNORECASE)


def currency() -> str:
    """The project currency: the operator's, else the BOQ's own declaration."""
    try:
        return money_settings.currency()
    except money_settings.MoneySettingMissing:
        pass
    lines = sources.boq_csv().splitlines()
    match = _BOQ_CURRENCY.search(lines[0] if lines else "")
    if match:
        return match.group(1).upper()
    raise money_settings.MoneySettingMissing(
        "no currency declared (PLATFORM_CURRENCY) and the BOQ states none"
    )


def tenant_scope() -> str:
    """The tenant the current request was authenticated as."""
    from app.tenancy import DEFAULT_TENANT, current_tenant_id

    return current_tenant_id() or DEFAULT_TENANT


def authority(capability_id: str, layer: int, name: str) -> Dict[str, Any]:
    return {
        "layer": int(layer),
        "name": str(name),
        "source": "app/actions/%s.py" % capability_id,
        "precedence": "precedence.v1",
    }


def nested_refusals(block_id: str, answer: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(answer, dict):
        return out
    for step in answer.get("results") or []:
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
    return out


def refusal(capability_id: str, label: Dict[str, Any], refusals: Sequence[str],
            answers: Dict[str, Any], input_digest: str | None = None,
            **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ok": False,
        "capability": capability_id,
        "error": "; ".join(str(item) for item in refusals)[:600],
        "blocks": answers,
        "authority": dict(label),
    }
    if input_digest:
        body["input_digest"] = input_digest
    body.update(extra)
    return body


def success(capability_id: str, label: Dict[str, Any], answers: Dict[str, Any],
            input_digest: str | None = None, **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ok": True,
        "capability": capability_id,
        "blocks": answers,
        "authority": dict(label),
    }
    if input_digest:
        body["input_digest"] = input_digest
    body.update(extra)
    return body


def summary_of(record: Dict[str, Any], keys: Sequence[str]) -> str:
    parts = [
        "%s=%s" % (key, record.get(key))
        for key in keys
        if record.get(key) not in (None, "", 0, 0.0, False)
    ]
    return "; ".join(parts)[:500] or "record"
