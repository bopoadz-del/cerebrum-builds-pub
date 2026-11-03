"""Shared helpers for the action handlers.

Currency, country and tax come from app.money_settings at the point of
use; a money path with no currency declared returns WITHHELD rather than
choosing one. Contract figures are named, operator-settable settings whose
defaults are the clauses of the uploaded contract excerpt.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, Optional

from app import dispatch, money_settings

#: Precedence ladder layer 2 -- the contract/BOQ documents are the source
#: of record. Every answer states which authority produced it.
AUTHORITY_DOCUMENTS = "2:documents"
AUTHORITY_CONTRACT = "document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf"


class BlockCallFailed(RuntimeError):
    def __init__(self, block_id: str, reason: str):
        super().__init__(f"{block_id}: {reason}")
        self.block_id = block_id
        self.reason = reason


def currency() -> str:
    try:
        return money_settings.currency()
    except money_settings.MoneySettingMissing:
        return "WITHHELD"


def clause_setting(env_name: str, contract_default: float) -> float:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return float(contract_default)
    return float(raw)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def as_date(value: Any, default: Optional[date] = None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return default or date(2026, 9, 3)


def round_money(value: float) -> float:
    return round(float(value), 2)


def call_block(block_id: str, payload: Dict[str, Any],
               action: Optional[str] = None,
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute one bound block; a refusal is raised, never swallowed."""
    try:
        answer = dispatch.execute(block_id, payload, action=action, params=params)
    except Exception as exc:  # noqa: BLE001 -- a block failure is a refusal
        raise BlockCallFailed(block_id, f"{type(exc).__name__}: {exc}") from exc
    reason = dispatch.refused(answer)
    if reason:
        raise BlockCallFailed(block_id, reason)
    return answer


def refused(capability_id: str, error: BlockCallFailed) -> Dict[str, Any]:
    return {
        "ok": False,
        "capability_id": capability_id,
        "block": error.block_id,
        "error": error.reason,
        "authority": AUTHORITY_DOCUMENTS,
    }


def answer(capability_id: str, result: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    body = {
        "ok": True,
        "capability_id": capability_id,
        "result": result,
        "authority": AUTHORITY_DOCUMENTS,
        "source": AUTHORITY_CONTRACT,
    }
    body.update(extra)
    return body
