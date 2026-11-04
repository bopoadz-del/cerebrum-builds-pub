"""Capability models: the declared contract every route, probe and suite reads.

Each model declares the fields it accepts, the vocabulary and bounds it
enforces, and the entity its records persist to.  ``FIELDS`` is the single
source the Factory's payload builder samples, so a value the platform refuses
must be declared here (``allowed_values``, ``required``, ``min``/``max``)
rather than left to prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

STATUS_VALUES = ["open", "in_progress", "closed"]

#: Order the platform publishes capabilities in; the S12 driver's default.
CAPABILITY_ORDER: List[str] = [
    "document_register",
    "progress_claims",
    "delay_damages_tracking",
    "qa_itp_records",
    "contract_clause_governance",
    "payment_security_and_retention_ledger",
    "claims_analytics_dashboard",
]


class ModelBase:
    CAPABILITY_ID = ""
    ENTITY = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    TYPES: Dict[str, str] = {}

    @classmethod
    def defaults(cls) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name in cls.FIELDS:
            rules = cls.CONSTRAINTS.get(name) or {}
            if "default" in rules:
                out[name] = rules["default"]
        return out

    @classmethod
    def validate(cls, payload: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """(clean record, rejection).  A rejection is data, never prose."""
        data = dict(payload or {})
        clean: Dict[str, Any] = {}
        for name in cls.FIELDS:
            rules = cls.CONSTRAINTS.get(name) or {}
            value = data.get(name)
            if value in (None, "") and rules.get("required"):
                return {}, {
                    "rejected_field": name,
                    "rejection_reason": "missing_required",
                    "allowed_values": rules.get("allowed_values"),
                    "detail": "%s is required" % name,
                }
            if value in (None, ""):
                if "default" in rules:
                    clean[name] = rules["default"]
                continue
            kind = cls.TYPES.get(name, "str")
            if kind in ("int", "float"):
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    return {}, {
                        "rejected_field": name,
                        "rejection_reason": "wrong_type",
                        "detail": "%s must be a number" % name,
                    }
                if kind == "int":
                    if number != int(number):
                        return {}, {
                            "rejected_field": name,
                            "rejection_reason": "wrong_type",
                            "detail": "%s must be an integer" % name,
                        }
                    number = int(number)
                clean[name] = number
            elif kind == "bool":
                clean[name] = bool(value)
            elif kind == "date":
                try:
                    date.fromisoformat(str(value))
                except ValueError:
                    return {}, {
                        "rejected_field": name,
                        "rejection_reason": "wrong_type",
                        "detail": "%s must be an ISO date (YYYY-MM-DD)" % name,
                    }
                clean[name] = str(value)
            else:
                clean[name] = str(value)
            allowed = rules.get("allowed_values")
            if allowed and clean[name] not in allowed:
                return {}, {
                    "rejected_field": name,
                    "rejection_reason": "not_allowed",
                    "allowed_values": list(allowed),
                    "detail": "%s must be one of: %s" % (name, ", ".join(str(a) for a in allowed)),
                }
            low = rules.get("min")
            high = rules.get("max")
            if isinstance(clean[name], (int, float)) and not isinstance(clean[name], bool):
                if low is not None and clean[name] < low:
                    return {}, {
                        "rejected_field": name,
                        "rejection_reason": "below_minimum",
                        "detail": "%s must be >= %s" % (name, low),
                    }
                if high is not None and clean[name] > high:
                    return {}, {
                        "rejected_field": name,
                        "rejection_reason": "above_maximum",
                        "detail": "%s must be <= %s" % (name, high),
                    }
        return clean, None

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "ModelBase":
        """Build an instance from a (possibly partial) record.

        Required-field enforcement belongs to ``validate()``, which the route
        calls on the caller's payload; the constructor itself must be able to
        represent a record that is not stored yet (``id`` None).
        """
        clean, rejection = cls.validate(payload)
        if rejection is not None:
            data = cls.defaults()
            data.update({k: v for k, v in (payload or {}).items() if k in cls.FIELDS})
            return cls(**data)
        return cls(**clean)

    def to_dict(self) -> Dict[str, Any]:
        out = {name: getattr(self, name) for name in self.FIELDS if hasattr(self, name)}
        out["id"] = getattr(self, "id", None)
        out["tenant_id"] = getattr(self, "tenant_id", None)
        return out


def _status() -> Dict[str, Any]:
    """The envelope status: a declared vocabulary with a default, so a caller
    that omits it gets an open record rather than a refusal."""
    return {"allowed_values": list(STATUS_VALUES), "default": "open"}


@dataclass
class DocumentRegister(ModelBase):
    CAPABILITY_ID = "document_register"
    ENTITY = "document_register"
    FIELDS = [
        "reference", "status", "document_type", "revision", "supersedes",
        "approval_state", "source_text",
    ]
    TYPES = {
        "reference": "str", "status": "str", "document_type": "str",
        "revision": "str", "supersedes": "str", "approval_state": "str",
        "source_text": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "document_type": {
            "allowed_values": ["drawing", "specification", "correspondence", "register", "certificate"],
            "default": "drawing",
        },
        "revision": {"default": "A"},
        "supersedes": {"default": ""},
        "approval_state": {"allowed_values": ["pending", "approved", "superseded"], "default": "pending"},
        "source_text": {"default": ""},
    }
    reference: str = ""
    status: str = "open"
    document_type: str = "drawing"
    revision: str = "A"
    supersedes: str = ""
    approval_state: str = "pending"
    source_text: str = ""
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class ProgressClaims(ModelBase):
    CAPABILITY_ID = "progress_claims"
    ENTITY = "progress_claims"
    FIELDS = [
        "reference", "status", "ipc_number", "boq_item", "measured_quantity",
        "boq_rate", "retention_rate", "amount_certified", "retention_held",
        "approval_state", "source_text",
    ]
    TYPES = {
        "reference": "str", "status": "str", "ipc_number": "str", "boq_item": "str",
        "measured_quantity": "float", "boq_rate": "float", "retention_rate": "float",
        "amount_certified": "float", "retention_held": "float",
        "approval_state": "str", "source_text": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "ipc_number": {"default": ""},
        "boq_item": {"default": ""},
        "measured_quantity": {"min": 0, "default": 0.0},
        "boq_rate": {"min": 0, "default": 0.0},
        "retention_rate": {"min": 0, "max": 1, "default": 0.05},
        "amount_certified": {"min": 0, "default": 0.0},
        "retention_held": {"min": 0, "default": 0.0},
        "approval_state": {"allowed_values": ["pending", "approved", "rejected"], "default": "pending"},
        "source_text": {"default": ""},
    }
    reference: str = ""
    status: str = "open"
    ipc_number: str = ""
    boq_item: str = ""
    measured_quantity: float = 0.0
    boq_rate: float = 0.0
    retention_rate: float = 0.05
    amount_certified: float = 0.0
    retention_held: float = 0.0
    approval_state: str = "pending"
    source_text: str = ""
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class DelayDamagesTracking(ModelBase):
    CAPABILITY_ID = "delay_damages_tracking"
    ENTITY = "delay_damages_tracking"
    FIELDS = [
        "reference", "status", "commencement_date", "delay_days",
        "accepted_contract_amount", "delay_damages_rate", "damages_cap_ratio",
        "damages_assessed",
    ]
    TYPES = {
        "reference": "str", "status": "str", "commencement_date": "date",
        "delay_days": "int", "accepted_contract_amount": "float",
        "delay_damages_rate": "float", "damages_cap_ratio": "float",
        "damages_assessed": "float",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "commencement_date": {"default": ""},
        "delay_days": {"min": 0, "default": 0},
        "accepted_contract_amount": {"min": 0, "default": 0.0},
        "delay_damages_rate": {"min": 0, "max": 1, "default": 0.001},
        "damages_cap_ratio": {"min": 0, "max": 1, "default": 0.1},
        "damages_assessed": {"min": 0, "default": 0.0},
    }
    reference: str = ""
    status: str = "open"
    commencement_date: Optional[date] = ""
    delay_days: int = 0
    accepted_contract_amount: float = 0.0
    delay_damages_rate: float = 0.001
    damages_cap_ratio: float = 0.1
    damages_assessed: float = 0.0
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class QAITPRecords(ModelBase):
    CAPABILITY_ID = "qa_itp_records"
    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference", "status", "inspection_type", "boq_item", "outcome",
        "evidence_digest", "chain_verified", "source_text",
    ]
    TYPES = {
        "reference": "str", "status": "str", "inspection_type": "str",
        "boq_item": "str", "outcome": "str", "evidence_digest": "str",
        "chain_verified": "bool", "source_text": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "inspection_type": {
            "allowed_values": ["earthworks", "concrete", "services", "finishing"],
            "default": "earthworks",
        },
        "boq_item": {"default": ""},
        "outcome": {"allowed_values": ["pass", "fail", "hold"], "default": "pass"},
        "evidence_digest": {"default": ""},
        "chain_verified": {"default": False},
        "source_text": {"default": ""},
    }
    reference: str = ""
    status: str = "open"
    inspection_type: str = "earthworks"
    boq_item: str = ""
    outcome: str = "pass"
    evidence_digest: str = ""
    chain_verified: bool = False
    source_text: str = ""
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class ContractClauseGovernance(ModelBase):
    CAPABILITY_ID = "contract_clause_governance"
    ENTITY = "contract_clause_governance"
    FIELDS = [
        "reference", "status", "clause_id", "clause_type", "source_text",
        "evidence_ref", "governance_state",
    ]
    TYPES = {
        "reference": "str", "status": "str", "clause_id": "str",
        "clause_type": "str", "source_text": "str", "evidence_ref": "str",
        "governance_state": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "clause_id": {"default": ""},
        "clause_type": {
            "allowed_values": [
                "delay_damages", "retention", "performance_security",
                "defects_notification", "time_for_completion",
            ],
            "default": "delay_damages",
        },
        "source_text": {"default": ""},
        "evidence_ref": {"required": True},
        "governance_state": {"allowed_values": ["requested", "approved", "refused"], "default": "requested"},
    }
    reference: str = ""
    status: str = "open"
    clause_id: str = ""
    clause_type: str = "delay_damages"
    source_text: str = ""
    evidence_ref: str = ""
    governance_state: str = "requested"
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class PaymentSecurityAndRetentionLedger(ModelBase):
    CAPABILITY_ID = "payment_security_and_retention_ledger"
    ENTITY = "payment_security_and_retention_ledger"
    FIELDS = [
        "reference", "status", "entry_type", "accepted_contract_amount",
        "performance_security_rate", "retention_rate", "amount_held",
        "lifecycle_state",
    ]
    TYPES = {
        "reference": "str", "status": "str", "entry_type": "str",
        "accepted_contract_amount": "float", "performance_security_rate": "float",
        "retention_rate": "float", "amount_held": "float", "lifecycle_state": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "entry_type": {
            "allowed_values": ["performance_security", "retention", "release"],
            "default": "performance_security",
        },
        "accepted_contract_amount": {"min": 0, "default": 0.0},
        "performance_security_rate": {"min": 0, "max": 1, "default": 0.10},
        "retention_rate": {"min": 0, "max": 1, "default": 0.05},
        "amount_held": {"min": 0, "default": 0.0},
        "lifecycle_state": {
            "allowed_values": ["created", "offered", "accepted", "paid", "delivered", "completed"],
            "default": "created",
        },
    }
    reference: str = ""
    status: str = "open"
    entry_type: str = "performance_security"
    accepted_contract_amount: float = 0.0
    performance_security_rate: float = 0.10
    retention_rate: float = 0.05
    amount_held: float = 0.0
    lifecycle_state: str = "created"
    id: Optional[int] = None
    tenant_id: Optional[str] = None


@dataclass
class ClaimsAnalyticsDashboard(ModelBase):
    CAPABILITY_ID = "claims_analytics_dashboard"
    ENTITY = "claims_analytics_dashboard"
    FIELDS = [
        "reference", "status", "period", "claims_count", "certified_total",
        "retention_total", "earned_value", "delay_days", "boq_source_text",
    ]
    TYPES = {
        "reference": "str", "status": "str", "period": "str", "claims_count": "int",
        "certified_total": "float", "retention_total": "float",
        "earned_value": "float", "delay_days": "int", "boq_source_text": "str",
    }
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": _status(),
        "period": {"default": ""},
        "claims_count": {"min": 0, "default": 0},
        "certified_total": {"min": 0, "default": 0.0},
        "retention_total": {"min": 0, "default": 0.0},
        "earned_value": {"min": 0, "default": 0.0},
        "delay_days": {"min": 0, "default": 0},
        "boq_source_text": {"default": ""},
    }
    reference: str = ""
    status: str = "open"
    period: str = ""
    claims_count: int = 0
    certified_total: float = 0.0
    retention_total: float = 0.0
    earned_value: float = 0.0
    delay_days: int = 0
    boq_source_text: str = ""
    id: Optional[int] = None
    tenant_id: Optional[str] = None


MODELS = {
    cls.CAPABILITY_ID: cls
    for cls in (
        DocumentRegister,
        ProgressClaims,
        DelayDamagesTracking,
        QAITPRecords,
        ContractClauseGovernance,
        PaymentSecurityAndRetentionLedger,
        ClaimsAnalyticsDashboard,
    )
}

ENTITY_NAMES: List[str] = list(MODELS) + ["work_queue", "idempotency", "retrieval_chunk", "lifecycle_audit"]
