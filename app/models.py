"""Capability models for the Harbourline contracts-administration platform.

Every capability declares its own ``FIELDS`` and ``CONSTRAINTS``. The writer
gate, the HTTP routes and the pilot suites build a payload from this
declaration, so a field a handler requires must be declared here and nowhere
else. ``to_dict()`` always exposes ``id`` (``None`` until stored).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar, Dict, List, Optional, Tuple

STATUS_VALUES: List[str] = ["open", "in_progress", "closed"]
RESERVED_KEYS = frozenset({"action", "id"})
MONEY_KINDS = ("money",)
QUANTITY_KINDS = ("quantity",)


@dataclass
class BaseRecord:
    """Shared envelope + storage contract. Entity name == capability id."""

    id: Optional[int] = None

    ENTITY: ClassVar[str] = ""
    FIELDS: ClassVar[List[str]] = []
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {}
    MONEY_FIELDS: ClassVar[Tuple[str, ...]] = ()
    QUANTITY_FIELDS: ClassVar[Tuple[str, ...]] = ()

    def to_dict(self) -> Dict[str, Any]:
        out = dataclasses.asdict(self)
        out["id"] = None if self.id is None else int(self.id)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseRecord":
        data = data or {}
        kwargs: Dict[str, Any] = {}
        for name in cls.FIELDS:
            if name in data:
                kwargs[name] = data[name]
        if data.get("id") is not None:
            try:
                kwargs["id"] = int(data["id"])
            except (TypeError, ValueError):
                kwargs["id"] = None
        return cls(**kwargs)

    @classmethod
    def money_fields(cls) -> Tuple[str, ...]:
        return tuple(
            name
            for name in cls.FIELDS
            if (cls.CONSTRAINTS.get(name) or {}).get("type") in MONEY_KINDS
        )

    @classmethod
    def quantity_fields(cls) -> Tuple[str, ...]:
        return tuple(
            name
            for name in cls.FIELDS
            if (cls.CONSTRAINTS.get(name) or {}).get("type") in QUANTITY_KINDS
        )


def _money(**extra: Any) -> Dict[str, Any]:
    return {"type": "money", "min": 0, **extra}


def _quantity(**extra: Any) -> Dict[str, Any]:
    return {"type": "quantity", "min": 0, **extra}


def _required(*extra: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"required": True}
    for item in extra:
        out.update(item)
    return out


@dataclass
class ProgressClaim(BaseRecord):
    """An Interim Payment Certificate assessed against BOQ measured quantities."""

    ENTITY: ClassVar[str] = "progress_claim_processing"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "claim_number", "claim_period", "boq_item",
        "measured_quantity", "boq_rate", "accepted_contract_amount",
        "certified_amount", "retention_percent", "retention_amount",
        "taking_over_date", "defects_end_date", "net_payable", "clause_citation",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "claim_number": {"type": "str"},
        "claim_period": {"type": "date"},
        "boq_item": {"type": "str"},
        "measured_quantity": _quantity(),
        "boq_rate": {"type": "money", "min": 0},
        "accepted_contract_amount": _money(),
        "certified_amount": _money(),
        "retention_percent": _quantity(),
        "retention_amount": _money(),
        "taking_over_date": {"type": "date"},
        "defects_end_date": {"type": "date"},
        "net_payable": _money(),
        "clause_citation": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    claim_number: str = ""
    claim_period: Optional[str] = None
    boq_item: str = ""
    measured_quantity: float = 0.0
    boq_rate: float = 0.0
    accepted_contract_amount: float = 0.0
    certified_amount: float = 0.0
    retention_percent: float = 0.0
    retention_amount: float = 0.0
    taking_over_date: Optional[str] = None
    defects_end_date: Optional[str] = None
    net_payable: float = 0.0
    clause_citation: str = ""


@dataclass
class DelayDamages(BaseRecord):
    """Running exposure under the Time for Completion and Delay Damages clauses."""

    ENTITY: ClassVar[str] = "delay_damages_tracking"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "notice_reference", "commencement_date",
        "event_date", "delay_days", "extension_days", "accepted_contract_amount",
        "delay_damages_amount", "delay_damages_cap", "exposure_ratio",
        "clause_citation",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "notice_reference": {"type": "str"},
        "commencement_date": {"type": "date"},
        "event_date": {"type": "date"},
        "delay_days": _quantity(),
        "extension_days": _quantity(),
        "accepted_contract_amount": _money(),
        "delay_damages_amount": _money(),
        "delay_damages_cap": _money(),
        "exposure_ratio": _quantity(),
        "clause_citation": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    notice_reference: str = ""
    commencement_date: Optional[str] = None
    event_date: Optional[str] = None
    delay_days: float = 0.0
    extension_days: float = 0.0
    accepted_contract_amount: float = 0.0
    delay_damages_amount: float = 0.0
    delay_damages_cap: float = 0.0
    exposure_ratio: float = 0.0
    clause_citation: str = ""


@dataclass
class QaItpRecord(BaseRecord):
    """An Inspection and Test Plan record linked to a BOQ item."""

    ENTITY: ClassVar[str] = "qa_itp_records"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "itp_number", "boq_item", "inspection_type",
        "inspection_date", "result", "hold_point",
        "document_reference", "pipeline_status",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "itp_number": {"type": "str"},
        "boq_item": {"type": "str"},
        "inspection_type": {"type": "str"},
        "inspection_date": {"type": "date"},
        "result": {"type": "str"},
        "hold_point": {"type": "bool"},
        "document_reference": {"type": "str"},
        "pipeline_status": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    itp_number: str = ""
    boq_item: str = ""
    inspection_type: str = ""
    inspection_date: Optional[str] = None
    result: str = ""
    hold_point: bool = False
    document_reference: str = ""
    pipeline_status: str = ""


@dataclass
class DocumentRegisterEntry(BaseRecord):
    """A controlled register entry: hashed, versioned, clause-linked."""

    ENTITY: ClassVar[str] = "document_register"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "document_title", "document_type",
        "document_revision", "issued_date", "file_name", "sha256",
        "supersedes", "linked_clause", "audit_hash",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "document_title": {"type": "str"},
        "document_type": {"type": "str"},
        "document_revision": {"type": "str"},
        "issued_date": {"type": "date"},
        "file_name": {"type": "str"},
        "sha256": {"type": "str"},
        "supersedes": {"type": "str"},
        "linked_clause": {"type": "str"},
        "audit_hash": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    document_title: str = ""
    document_type: str = ""
    document_revision: str = ""
    issued_date: Optional[str] = None
    file_name: str = ""
    sha256: str = ""
    supersedes: str = ""
    linked_clause: str = ""
    audit_hash: str = ""


@dataclass
class ContractClauseGrounding(BaseRecord):
    """A grounded answer over the uploaded contract and BOQ corpus."""

    ENTITY: ClassVar[str] = "contract_clause_grounding"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "question", "clause_reference",
        "document_reference", "authority_layer", "evidence_count", "answered",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "question": {"type": "str"},
        "clause_reference": {"type": "str"},
        "document_reference": {"type": "str"},
        "authority_layer": {"type": "str"},
        "evidence_count": {"type": "int", "min": 0},
        "answered": {"type": "bool"},
    }
    reference: str = ""
    status: str = "open"
    question: str = ""
    clause_reference: str = ""
    document_reference: str = ""
    authority_layer: str = ""
    evidence_count: int = 0
    answered: bool = False


@dataclass
class PerformanceSecurity(BaseRecord):
    """The Clause 4.2 Performance Security: issue, expiry, cover."""

    ENTITY: ClassVar[str] = "performance_security_tracking"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "security_number", "provider", "issued_date",
        "expiry_date", "accepted_contract_amount", "required_amount",
        "secured_amount", "coverage_ratio", "renewal_notice_days",
        "days_to_expiry", "clause_citation",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "security_number": {"type": "str"},
        "provider": {"type": "str"},
        "issued_date": {"type": "date"},
        "expiry_date": {"type": "date"},
        "accepted_contract_amount": _money(),
        "required_amount": _money(),
        "secured_amount": _money(),
        "coverage_ratio": _quantity(),
        "renewal_notice_days": _quantity(),
        "days_to_expiry": {"type": "int", "min": 0},
        "clause_citation": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    security_number: str = ""
    provider: str = ""
    issued_date: Optional[str] = None
    expiry_date: Optional[str] = None
    accepted_contract_amount: float = 0.0
    required_amount: float = 0.0
    secured_amount: float = 0.0
    coverage_ratio: float = 0.0
    renewal_notice_days: float = 0.0
    days_to_expiry: int = 0
    clause_citation: str = ""


@dataclass
class ComplianceDashboard(BaseRecord):
    """The project's single compliance view, with drill-down references."""

    ENTITY: ClassVar[str] = "compliance_dashboard"
    FIELDS: ClassVar[List[str]] = [
        "reference", "status", "period", "claims_open", "delay_exposure",
        "itp_completion_ratio", "documents_registered", "security_valid",
        "clause_citation", "snapshot",
    ]
    CONSTRAINTS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "reference": _required(),
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": True},
        "period": {"type": "str"},
        "claims_open": {"type": "int", "min": 0},
        "delay_exposure": _money(),
        "itp_completion_ratio": _quantity(),
        "documents_registered": {"type": "int", "min": 0},
        "security_valid": {"type": "bool"},
        "clause_citation": {"type": "str"},
        "snapshot": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    period: str = ""
    claims_open: int = 0
    delay_exposure: float = 0.0
    itp_completion_ratio: float = 0.0
    documents_registered: int = 0
    security_valid: bool = False
    clause_citation: str = ""
    snapshot: str = ""


MODELS: Dict[str, Any] = {
    ProgressClaim.ENTITY: ProgressClaim,
    DelayDamages.ENTITY: DelayDamages,
    QaItpRecord.ENTITY: QaItpRecord,
    DocumentRegisterEntry.ENTITY: DocumentRegisterEntry,
    ContractClauseGrounding.ENTITY: ContractClauseGrounding,
    PerformanceSecurity.ENTITY: PerformanceSecurity,
    ComplianceDashboard.ENTITY: ComplianceDashboard,
}

#: Entity name -> ordered column names the JSON payload may carry.
COLUMNS: Dict[str, List[str]] = {cap: list(cls.FIELDS) for cap, cls in MODELS.items()}


class ValidationError(ValueError):
    """A payload the capability's own declaration refuses."""

    def __init__(self, field_name: str, reason: str, allowed: Optional[List[Any]] = None):
        self.field = field_name
        self.reason = reason
        self.allowed = list(allowed or [])
        super().__init__("%s: %s" % (field_name, reason))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rejected_field": self.field,
            "rejection_reason": self.reason,
            "allowed_values": self.allowed,
        }


def validate_payload(capability_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a request against the capability's own FIELDS/CONSTRAINTS.

    Raises ValidationError; returns the cleaned record on success.
    """
    cls = MODELS.get(capability_id)
    if cls is None:
        raise ValidationError("capability_id", "not_allowed", sorted(MODELS))
    if not isinstance(payload, dict):
        raise ValidationError("payload", "wrong_type")
    for key in payload:
        if key in RESERVED_KEYS:
            raise ValidationError(str(key), "reserved_key")
    clean: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = cls.CONSTRAINTS.get(name) or {}
        if name not in payload or payload[name] in (None, ""):
            if rules.get("required"):
                raise ValidationError(name, "missing_required")
            continue
        value = payload[name]
        allowed = rules.get("allowed_values")
        if allowed and value not in allowed:
            raise ValidationError(name, "not_allowed", allowed)
        kind = str(rules.get("type") or "str")
        if kind in ("int", "float", "money", "quantity"):
            if isinstance(value, bool):
                raise ValidationError(name, "wrong_type")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValidationError(name, "wrong_type")
            low = rules.get("min")
            if low is not None and number < float(low):
                raise ValidationError(name, "below_min")
            clean[name] = int(number) if kind == "int" else number
        elif kind == "bool":
            if not isinstance(value, bool):
                raise ValidationError(name, "wrong_type")
            clean[name] = value
        elif kind in ("date", "datetime", "time"):
            text = str(value)
            try:
                if kind == "date":
                    date.fromisoformat(text[:10])
                elif kind == "datetime":
                    datetime.fromisoformat(text)
            except ValueError:
                raise ValidationError(name, "wrong_format")
            clean[name] = text
        else:
            clean[name] = str(value)
    return clean


def model_for(capability_id: str):
    return MODELS.get(capability_id)
