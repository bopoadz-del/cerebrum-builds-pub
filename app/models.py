"""Declared capability contracts: the sample a payload builder emits.

Every capability has one dataclass here. FIELDS lists the declarable
columns, CONSTRAINTS the vocabulary/bounds a payload must honour, and
ENTITY the alembic table and store entity the record is persisted to.
Money is declared with format "money" and quantities with "quantity";
currency and rates are read at use, never typed in here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List

STATUS_VALUES = ["open", "in_progress", "closed"]

class RecordModel:
    """Shared envelope: from_dict/to_dict for every capability model.

    ``id`` is None until the store assigns it; to_dict() always exposes it
    because a caller reads the stored record's identifier back from here.
    """

    id = None
    ENTITY = ""
    FIELDS: List[str] = []
    MONEY_FIELDS: List[str] = []
    QUANTITY_FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        instance = cls()
        for key, value in dict(data or {}).items():
            if key == "id" or key in cls.FIELDS:
                setattr(instance, key, value)
        return instance

    def to_dict(self) -> Dict[str, Any]:
        body = {name: getattr(self, name, None) for name in self.FIELDS}
        body["id"] = getattr(self, "id", None)
        return body



@dataclass
class ProgressClaim(RecordModel):
    reference: str = "sample"
    status: str = "open"
    ipc_number: str = "sample"
    boq_item: str = "sample"
    period: str = "sample"
    gross_amount: float = 1.5
    retention_amount: float = 1.5
    net_certified: float = 1.5
    currency: str = "sample"

    ENTITY = "progress_claims"
    FIELDS = ["reference", "status", "ipc_number", "boq_item", "period",
              "gross_amount", "retention_amount", "net_certified", "currency"]
    MONEY_FIELDS = ["gross_amount", "retention_amount", "net_certified"]
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }


@dataclass
class DelayDamagesTracking(RecordModel):
    reference: str = "sample"
    status: str = "open"
    commencement_date: date = date(2026, 9, 3)
    completion_date: date = date(2026, 9, 3)
    accepted_contract_amount: float = 1.5
    delay_days: int = 1
    delay_damages: float = 1.5
    cap_reached: bool = False

    ENTITY = "delay_damages_tracking"
    FIELDS = ["reference", "status", "commencement_date", "completion_date",
              "accepted_contract_amount", "delay_days", "delay_damages", "cap_reached"]
    MONEY_FIELDS = ["accepted_contract_amount", "delay_damages"]
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "delay_days": {"min": 0},
    }


@dataclass
class QaItpRecord(RecordModel):
    reference: str = "sample"
    status: str = "open"
    boq_item: str = "sample"
    inspection_lot: str = "sample"
    hold_point: str = "sample"
    witness_point: str = "sample"
    test_result: str = "sample"
    inspection_date: date = date(2026, 9, 3)

    ENTITY = "qa_itp_records"
    FIELDS = ["reference", "status", "boq_item", "inspection_lot", "hold_point",
              "witness_point", "test_result", "inspection_date"]
    MONEY_FIELDS = []
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }


@dataclass
class DocumentRegister(RecordModel):
    reference: str = "sample"
    status: str = "open"
    title: str = "sample"
    revision: str = "sample"
    document_type: str = "sample"
    source_filename: str = "sample"
    checksum: str = "sample"
    issued_date: date = date(2026, 9, 3)

    ENTITY = "document_register"
    FIELDS = ["reference", "status", "title", "revision", "document_type",
              "source_filename", "checksum", "issued_date"]
    MONEY_FIELDS = []
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "document_type": {"allowed_values": ["contract", "boq", "drawing", "report", "certificate"]},
    }


@dataclass
class PerformanceSecurityTracking(RecordModel):
    reference: str = "sample"
    status: str = "open"
    instrument_number: str = "sample"
    accepted_contract_amount: float = 1.5
    security_amount: float = 1.5
    expiry_date: date = date(2026, 9, 3)
    issuer: str = "sample"

    ENTITY = "performance_security_tracking"
    FIELDS = ["reference", "status", "instrument_number", "accepted_contract_amount",
              "security_amount", "expiry_date", "issuer"]
    MONEY_FIELDS = ["accepted_contract_amount", "security_amount"]
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }


@dataclass
class DefectsNotificationPeriod(RecordModel):
    reference: str = "sample"
    status: str = "open"
    taking_over_date: date = date(2026, 9, 3)
    defect_ref: str = "sample"
    defect_description: str = "sample"
    closeout_evidence: str = "sample"
    retention_release_amount: float = 1.5

    ENTITY = "defects_notification_period"
    FIELDS = ["reference", "status", "taking_over_date", "defect_ref",
              "defect_description", "closeout_evidence", "retention_release_amount"]
    MONEY_FIELDS = ["retention_release_amount"]
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }


@dataclass
class ClaimEvidenceAndApprovals(RecordModel):
    reference: str = "sample"
    status: str = "open"
    claim_reference: str = "sample"
    evidence_ref: str = "sample"
    preparer_id: str = "sample"
    certifier_id: str = "sample"
    decision: str = "sample"
    claim_amount: float = 1.5
    retention_amount: float = 1.5
    net_certified: float = 1.5

    ENTITY = "claim_evidence_and_approvals"
    FIELDS = ["reference", "status", "claim_reference", "evidence_ref",
              "preparer_id", "certifier_id", "decision",
              "claim_amount", "retention_amount", "net_certified"]
    MONEY_FIELDS = ["claim_amount", "retention_amount", "net_certified"]
    QUANTITY_FIELDS = []
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "evidence_ref": {"required": True},
    }


MODELS: Dict[str, Any] = {
    "progress_claims": ProgressClaim,
    "delay_damages_tracking": DelayDamagesTracking,
    "qa_itp_records": QaItpRecord,
    "document_register": DocumentRegister,
    "performance_security_tracking": PerformanceSecurityTracking,
    "defects_notification_period": DefectsNotificationPeriod,
    "claim_evidence_and_approvals": ClaimEvidenceAndApprovals,
}


def fields_of(capability_id: str) -> List[Dict[str, Any]]:
    cls = MODELS[capability_id]
    return [
        {"name": name, "type": "str", **dict((cls.CONSTRAINTS or {}).get(name) or {})}
        for name in cls.FIELDS
    ]


def sample_payload(capability_id: str) -> Dict[str, Any]:
    cls = MODELS[capability_id]
    out: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = (cls.CONSTRAINTS or {}).get(name) or {}
        allowed = rules.get("allowed_values")
        if allowed:
            out[name] = allowed[0]
        else:
            out[name] = getattr(cls, name, "sample")
    return out
