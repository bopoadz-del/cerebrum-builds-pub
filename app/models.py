"""Declared capability models for Harbourline Civil Works.

Each model carries FIELDS + CONSTRAINTS, which the factory probe reads to build
a payload the route is expected to accept. Only ``reference`` and ``status`` are
required: every other field is derived from the contract/BOQ source of record or
defaulted by the handler. Field vocabularies and formats are declared here, never
enforced only in prose inside a handler.

Numeric declarations: the platform's kernel JSON contract speaks
string/integer/number/boolean, so money and quantity fields are declared
``float`` and carry the canonical markers ``money=True`` / ``quantity=True``
and their class-level ``MONEY_FIELDS`` / ``QUANTITY_FIELDS`` lists. Currency,
country and every rate are still read from ``app.money_settings`` at the point
of use -- no rate or currency is typed here.
"""

from __future__ import annotations

import copy
from datetime import date, datetime

STATUS_VALUES = ["open", "in_progress", "closed"]

DOCUMENT_TYPES = ["contract", "boq", "drawing", "specification", "itp", "correspondence"]
ITP_RESULTS = ["pass", "fail", "pending", "conditional"]
APPROVAL_STATES = ["draft", "submitted", "certified", "rejected"]


class _Model:
    """Small value object shared by the four capability models."""

    FIELDS: list[str] = []
    CONSTRAINTS: dict = {}
    MONEY_FIELDS: list[str] = []
    QUANTITY_FIELDS: list[str] = []
    ENTITY = ""

    def __init__(self, **values):
        self.id = values.pop("id", None)
        for name in self.FIELDS:
            setattr(self, name, values.pop(name, self.default_for(name)))
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def default_for(cls, name):
        rules = cls.CONSTRAINTS.get(name) or {}
        if rules.get("allowed_values"):
            return rules["allowed_values"][0]
        kind = rules.get("type")
        if kind == "int":
            return int(rules.get("min", 0) or 0)
        if kind in ("float", "money", "quantity"):
            return float(rules.get("min", 0.0) or 0.0)
        if kind == "bool":
            return False
        if kind == "date":
            return None
        return ""

    @classmethod
    def from_dict(cls, payload):
        data = copy.deepcopy(dict(payload or {}))
        obj = cls(
            id=data.pop("id", None),
            **{k: v for k, v in data.items() if k in cls.FIELDS},
        )
        return obj

    def to_dict(self):
        out = {"id": self.id}
        for name in self.FIELDS:
            out[name] = getattr(self, name, None)
        return out

    @classmethod
    def required_fields(cls):
        return [n for n in cls.FIELDS if (cls.CONSTRAINTS.get(n) or {}).get("required")]


def _f(name, kind="str", required=False, **extra):
    rules = {"type": kind, "required": required}
    rules.update(extra)
    return name, rules


def _constraints(*pairs):
    return dict(pairs)


class ProgressClaim(_Model):
    """Interim Payment Certificate prepared against BOQ items and Clause 14.3."""

    ENTITY = "progress_claim_administration"
    FIELDS = [
        "reference", "status", "claim_number", "period_from", "period_to",
        "boq_item_codes", "claimed_quantity", "unit_rate", "claimed_amount",
        "certified_amount", "retention_amount", "performance_security",
        "accepted_contract_amount", "line_items", "clause_reference",
    ]
    CONSTRAINTS = _constraints(
        _f("reference", "str", True),
        _f("status", "str", True, allowed_values=STATUS_VALUES),
        _f("claim_number", "str"),
        _f("period_from", "date"),
        _f("period_to", "date"),
        _f("boq_item_codes", "str"),
        _f("claimed_quantity", "float", min=0.0, quantity=True),
        _f("unit_rate", "float", min=0.0, money=True),
        _f("claimed_amount", "float", min=0.0, money=True),
        _f("certified_amount", "float", min=0.0, money=True),
        _f("retention_amount", "float", min=0.0, money=True),
        _f("performance_security", "float", min=0.0, money=True),
        _f("accepted_contract_amount", "float", min=0.0, money=True),
        _f("line_items", "str"),
        _f("clause_reference", "str"),
    )
    MONEY_FIELDS = ["unit_rate", "claimed_amount", "certified_amount", "retention_amount", "performance_security", "accepted_contract_amount"]
    QUANTITY_FIELDS = ["claimed_quantity"]


class DelayDamages(_Model):
    """Clause 8.7 delay-damages position for the project."""

    ENTITY = "delay_damages_tracking"
    FIELDS = [
        "reference", "status", "notice_reference", "commencement_date",
        "completion_date", "actual_completion_date", "accepted_contract_amount",
        "days_of_delay", "daily_rate", "damages_cap_ratio", "damages_amount",
        "clause_reference",
    ]
    CONSTRAINTS = _constraints(
        _f("reference", "str", True),
        _f("status", "str", True, allowed_values=STATUS_VALUES),
        _f("notice_reference", "str"),
        _f("commencement_date", "date"),
        _f("completion_date", "date"),
        _f("actual_completion_date", "date"),
        _f("accepted_contract_amount", "float", min=0.0, money=True),
        _f("days_of_delay", "int", min=0, quantity=True),
        _f("daily_rate", "float", min=0.0),
        _f("damages_cap_ratio", "float", min=0.0),
        _f("damages_amount", "float", min=0.0, money=True),
        _f("clause_reference", "str"),
    )
    MONEY_FIELDS = ["accepted_contract_amount", "damages_amount"]
    QUANTITY_FIELDS = ["days_of_delay"]


class QaItpRecord(_Model):
    """Inspection and Test Plan record linked to a BOQ item."""

    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference", "status", "itp_number", "inspection_type", "boq_item_code",
        "inspection_date", "result", "inspector", "notes", "evidence_text",
    ]
    CONSTRAINTS = _constraints(
        _f("reference", "str", True),
        _f("status", "str", True, allowed_values=STATUS_VALUES),
        _f("itp_number", "str"),
        _f("inspection_type", "str"),
        _f("boq_item_code", "str"),
        _f("inspection_date", "date"),
        _f("result", "str", allowed_values=ITP_RESULTS),
        _f("inspector", "str"),
        _f("notes", "str"),
        _f("evidence_text", "str"),
    )


class DocumentRegisterEntry(_Model):
    """Controlled document register entry with revision and provenance."""

    ENTITY = "document_register"
    FIELDS = [
        "reference", "status", "title", "document_type", "revision",
        "issued_date", "source_document", "checksum", "supersedes",
        "description", "search_query",
    ]
    CONSTRAINTS = _constraints(
        _f("reference", "str", True),
        _f("status", "str", True, allowed_values=STATUS_VALUES),
        _f("title", "str"),
        _f("document_type", "str", allowed_values=DOCUMENT_TYPES),
        _f("revision", "str"),
        _f("issued_date", "date"),
        _f("source_document", "str"),
        _f("checksum", "str"),
        _f("supersedes", "str"),
        _f("description", "str"),
        _f("search_query", "str"),
    )


MODELS = {
    "progress_claim_administration": ProgressClaim,
    "delay_damages_tracking": DelayDamages,
    "qa_itp_records": QaItpRecord,
    "document_register": DocumentRegisterEntry,
}

CAPABILITY_IDS = list(MODELS)


def coerce_value(capability_id, field, value):
    """Coerce one request value to the declared type. Raises ValueError."""
    if value is None:
        return None
    rules = (MODELS[capability_id].CONSTRAINTS.get(field) or {})
    if isinstance(value, str) and not value.strip():
        return None if not rules.get("required") else value
    kind = rules.get("type") or "str"
    if kind == "str":
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        allowed = rules.get("allowed_values")
        if allowed and value not in allowed:
            raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
        return value
    if kind in ("int", "number", "float", "money", "quantity"):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field} must be a number") from None
        if rules.get("min") is not None and number < float(rules["min"]):
            raise ValueError(f"{field} must be >= {rules['min']}")
        if rules.get("max") is not None and number > float(rules["max"]):
            raise ValueError(f"{field} must be <= {rules['max']}")
        return int(number) if kind == "int" else number
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        raise ValueError(f"{field} must be a boolean")
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from None
    return value
