"""Shared result helpers for capability handlers.

A handler returns the envelope ``{ok, record, id, result}``.  The route owns
persistence: it saves the request, fills ``record`` and ``id``, and never saves
anything when a block refused.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def ok(result: Optional[Dict[str, Any]] = None, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": True, "record": None, "id": None, "result": result or {}}
    out.update(extra)
    return out


def fail(message: str, error_kind: str = "block_refused", **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": str(message), "error_kind": error_kind}
    out.update(extra)
    return out


def block_failed(result: Any) -> bool:
    if not isinstance(result, dict):
        return True
    if result.get("status") == "error":
        return True
    return result.get("ok") is False and result.get("error_kind") != "unavailable"


def refusal_text(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("error") or result.get("message") or "block refused the input")[:300]
    return "block refused the input"


def as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any, default: int = 0) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def minutes(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def split_list(value: Any) -> list:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]
