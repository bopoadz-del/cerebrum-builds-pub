"""The contract excerpt and the priced BOQ: the platform's source of record.

Every certificate, claim and record is grounded in a clause or a BOQ item
from these two uploaded documents. Nothing here is invented: the content is
the customer's own document text, and every figure a customer owns (a rate,
a cap, a period) is a named setting an operator can change.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_TERMS_PATH = ROOT / "docs" / "contract_terms.json"
BOQ_ITEMS_PATH = ROOT / "docs" / "boq_items.json"


def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def contract_document() -> Dict[str, Any]:
    return _load(CONTRACT_TERMS_PATH)


def boq_document() -> Dict[str, Any]:
    return _load(BOQ_ITEMS_PATH)


def contract_document_id() -> str:
    return str(contract_document().get("document_id") or "")


def boq_document_id() -> str:
    return str(boq_document().get("document_id") or "")


def clauses() -> List[Dict[str, Any]]:
    return list(contract_document().get("clauses") or [])


def clause(ref: str) -> Optional[Dict[str, Any]]:
    wanted = str(ref or "").strip()
    for row in clauses():
        if row.get("ref") == wanted:
            return row
    return None


def clause_text(ref: str) -> str:
    row = clause(ref)
    if not row:
        return ""
    return f"Clause {row['ref']} {row.get('heading', '')}: {row.get('text', '')}".strip()


def boq_items() -> List[Dict[str, Any]]:
    return list(boq_document().get("items") or [])


def boq_item(code: str) -> Optional[Dict[str, Any]]:
    wanted = str(code or "").strip().upper()
    for row in boq_items():
        if str(row.get("item_code", "")).upper() == wanted:
            return row
    return None


def boq_total() -> Decimal:
    total = Decimal("0")
    for row in boq_items():
        total += Decimal(str(row.get("rate") or 0)) * Decimal(str(row.get("quantity") or 0))
    return total


def _declared_term(name: str) -> Optional[Decimal]:
    for row in clauses():
        if row.get("term") == name and row.get("value") is not None:
            return Decimal(str(row["value"]))
    return None


def term(name: str) -> Decimal:
    """A contract term the customer owns, settable by the operator.

    Precedence: PLATFORM_TERM_<NAME> in the deploy environment, else the value
    declared in the uploaded contract excerpt. No rate lives in code.
    """
    env = "PLATFORM_TERM_" + str(name).upper()
    raw = (os.environ.get(env) or "").strip()
    if raw:
        try:
            return Decimal(raw)
        except Exception as exc:  # noqa: BLE001 - a bad setting is a config error
            raise ValueError(f"{env} is not a decimal number: {raw!r}") from exc
    declared = _declared_term(str(name))
    if declared is None:
        raise KeyError(f"no contract term declared for {name!r} (set {env})")
    return declared


def term_int(name: str) -> int:
    return int(term(name))


def terms_snapshot() -> Dict[str, str]:
    names = [
        "time_for_completion_days",
        "delay_damages_daily_rate",
        "delay_damages_cap_rate",
        "defects_notification_days",
        "retention_rate",
        "retention_release_first_share",
        "performance_security_rate",
    ]
    out: Dict[str, str] = {}
    for name in names:
        try:
            out[name] = str(term(name))
        except KeyError:
            continue
    return out
