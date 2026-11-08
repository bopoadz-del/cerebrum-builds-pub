"""Shared, domain-neutral helpers for the capability handlers.

The HTTP route binds the authenticated request context (tenant + principal)
before it calls a handler; a direct ``handle()`` call outside a request falls
back to the platform tenant. No handler persists: persistence is the route's
tenant-scoped job.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from app.dispatch import error_text, failed

_REQUEST = contextvars.ContextVar("harbourline_request", default=None)


def bind_request(tenant_id: str, principal: str) -> None:
    _REQUEST.set({"tenant_id": str(tenant_id), "principal": str(principal)})


def request_context() -> Dict[str, str]:
    value = _REQUEST.get()
    if value:
        return dict(value)
    return {"tenant_id": "local", "principal": "contract-administrator"}


def require_payload(payload: Any) -> Dict[str, Any]:
    """Refuse an empty record: every capability needs at least one field.

    This is the fail-closed edge for a direct call (the HTTP route has already
    run the model's required-field validation). It is deliberately generic: an
    empty mapping carries no record to assess, seal, register or answer.
    """
    if not isinstance(payload, dict) or not payload:
        raise ValueError("a non-empty capability record is required")
    return dict(payload)


def input_digest(payload: Dict[str, Any]) -> str:
    """A stable audit fingerprint of the exact record the capability assessed."""
    encoded = json.dumps(payload or {}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def tenant_id() -> str:
    return request_context()["tenant_id"]


def principal() -> str:
    return request_context()["principal"]


def refusal(block_id: str, answer: Any) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "%s refused: %s" % (block_id, error_text(answer)),
        "block": block_id,
        "source": {
            "block": block_id,
            "status": (answer or {}).get("status") if isinstance(answer, dict) else None,
            "detail": answer if isinstance(answer, dict) else str(answer)[:300],
        },
    }


def check(block_id: str, answer: Any) -> Optional[Dict[str, Any]]:
    """None when the block succeeded, else the fail-closed refusal envelope."""
    if failed(answer, block_id):
        return refusal(block_id, answer)
    return None


def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    return int(as_float(value, default))


def as_date(value: Any, default: Optional[date] = None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return default or date.today()


def iso(value: date) -> str:
    return value.isoformat()


def add_days(start: date, days: float) -> date:
    return start + timedelta(days=int(days))


def round_money(value: float) -> float:
    return round(float(value or 0.0), 2)


def ok(**fields: Any) -> Dict[str, Any]:
    return {"ok": True, **fields}


def block_result(answer: Any) -> Any:
    """The payload a block answered, preferring its declared result key."""
    if not isinstance(answer, dict):
        return answer
    if "result" in answer and answer["result"] is not None:
        return answer["result"]
    return answer
