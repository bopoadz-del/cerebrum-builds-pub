"""Shared helpers for capability handlers (not a capability itself)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def block_failure(block_id: str, answer: Any) -> Optional[Dict[str, Any]]:
    """A typed refusal from a block, or None when the block answered."""
    if not isinstance(answer, dict):
        return {"ok": False, "error": f"{block_id} returned no result", "block": block_id}
    if answer.get("ok") is False or answer.get("status") in ("error", "failed", "refused"):
        message = answer.get("error") or answer.get("detail") or "block refused"
        return {"ok": False, "error": f"{block_id}: {message}", "block": block_id}
    return None


def envelope(result: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    body = dict(record or {})
    return {"ok": True, "id": body.get("id"), "result": result, "record": body}


def configured_email(payload: Dict[str, Any]) -> str:
    value = str(payload.get("manager_email") or "").strip()
    return value or "ops@example.com"


def token_from_env() -> str:
    return (os.getenv("PLATFORM_TOKEN") or "").strip()
