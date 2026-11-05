"""Capability models for the Harbourline Civil Works contracts platform.

Each model carries the FIELD list and CONSTRAINTS the routes, the handlers
and the emitted test payloads all read, so a payload built from the declared
contract is a payload the product accepts. Field vocabularies are the
customer's own: BOQ item codes from
document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx and clause
references from
document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

ENVELOPE_STATUS = ["open", "in_progress", "closed"]

#: Priced BOQ items, exactly as the uploaded bill of quantities prices them.
BOQ_ITEM_CODES = ["P1", "P2", "P3", "P4", "P5", "E1", "E2", "E3", "E4", "E5"]

#: The governing clauses of the uploaded contract excerpt.
CLAUSE_REFS = ["8.2", "8.7", "11.1", "14.3", "4.2"]

CONTRACT_DOC = "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"
BOQ_DOC = "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx"
SOURCE_DOCUMENTS = [CONTRACT_DOC, BOQ_DOC]


def _iso(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)


def _date(value: Any) -> Optional[_dt.date]:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class Model:
    """Shared behaviour: declaration-driven serialisation with a stable id."""

    ENTITY = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    _FIELD_PY: Dict[str, str] = {}

    def __init__(self, **values: Any):
        for name in self.FIELDS:
            setattr(self, name, values.get(name))
        self.id = values.get("id")

    # ---- declaration helpers -------------------------------------------
    @classmethod
    def required_fields(cls) -> List[str]:
        return [name for name in cls.FIELDS if (cls.CONSTRAINTS.get(name) or {}).get("required")]

    @classmethod
    def allowed_values(cls, name: str) -> List[Any]:
        return list((cls.CONSTRAINTS.get(name) or {}).get("allowed_values") or [])

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "Model":
        data = dict(payload or {})
        values = {}
        for name in cls.FIELDS:
            values[name] = data.get(name)
        values["id"] = data.get("id")
        return cls(**values)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name in self.FIELDS:
            value = getattr(self, name, None)
            if isinstance(value, (_dt.date, _dt.datetime)):
                value = value.isoformat()
            out[name] = value
        out["id"] = self.id
        return out

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} id={self.id!r} reference={getattr(self, 'reference', None)!r}>"


class ProgressClaim(Model):
    """Interim Payment Certificate against BOQ measured quantities.

    Retention is 5% of each certificate (Clause 14.3); the performance
    security is 10% of the Accepted Contract Amount (Clause 4.2). Both are
    operator settings, never numbers in code.
    """

    ENTITY = "progress_claims"
    FIELDS = [
        "reference",
        "status",
        "claim_number",
        "claim_period",
        "boq_item_code",
        "measured_quantity",
        "unit_rate",
        "accepted_contract_amount",
        "approval_decision",
        "approved_by",
        "certificate_note",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "claim_number": {"required": True, "type": "str"},
        "claim_period": {"type": "str"},
        "boq_item_code": {"required": True, "type": "str", "allowed_values": BOQ_ITEM_CODES},
        "measured_quantity": {"type": "float", "min": 0},
        "unit_rate": {"type": "float", "min": 0},
        "accepted_contract_amount": {"type": "float", "min": 0},
        "approval_decision": {"type": "str", "allowed_values": ["none", "certify", "reject"]},
        "approved_by": {"type": "str", "approval": True},
        "certificate_note": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    claim_number: str = ""
    claim_period: str = ""
    boq_item_code: str = ""
    measured_quantity: float = 0.0
    unit_rate: float = 0.0
    accepted_contract_amount: float = 0.0
    approval_decision: str = "none"
    approved_by: str = ""
    certificate_note: str = ""


class DelayDamagesAssessment(Model):
    """Time for Completion and delay damages.

    Time for Completion is 730 days from the Commencement Date (Clause 8.2).
    Damages are 0.1% of the Accepted Contract Amount per day of delay, capped
    at 10% (Clause 8.7). The rate, the cap and the time limit are settings.
    """

    ENTITY = "delay_damages_tracking"
    FIELDS = [
        "reference",
        "status",
        "assessment_number",
        "commencement_date",
        "completion_date",
        "days_of_delay",
        "accepted_contract_amount",
        "notice_served",
        "assessment_note",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "assessment_number": {"required": True, "type": "str"},
        "commencement_date": {"type": "date"},
        "completion_date": {"type": "date"},
        "days_of_delay": {"type": "int", "min": 0, "max": 36500},
        "accepted_contract_amount": {"type": "float", "min": 0},
        "notice_served": {"type": "bool"},
        "assessment_note": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    assessment_number: str = ""
    commencement_date: Optional[_dt.date] = None
    completion_date: Optional[_dt.date] = None
    days_of_delay: int = 0
    accepted_contract_amount: float = 0.0
    notice_served: bool = False
    assessment_note: str = ""


class QAItpRecord(Model):
    """Inspection and Test Plan record tied to BOQ work items."""

    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference",
        "status",
        "itp_number",
        "boq_item_code",
        "inspection_type",
        "hold_point",
        "inspection_date",
        "result",
        "signed_off_by",
        "remarks",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "itp_number": {"required": True, "type": "str"},
        "boq_item_code": {"type": "str", "allowed_values": BOQ_ITEM_CODES},
        "inspection_type": {
            "type": "str",
            "allowed_values": ["material", "workmanship", "hold_point", "witness_point", "final"],
        },
        "hold_point": {"type": "bool"},
        "inspection_date": {"type": "date"},
        "result": {"type": "str", "allowed_values": ["pending", "pass", "fail", "conditional"]},
        "signed_off_by": {"type": "str", "approval": True},
        "remarks": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    itp_number: str = ""
    boq_item_code: str = ""
    inspection_type: str = ""
    hold_point: bool = False
    inspection_date: Optional[_dt.date] = None
    result: str = "pending"
    signed_off_by: str = ""
    remarks: str = ""


class DocumentRegisterEntry(Model):
    """Controlled register of contract, BOQ, drawings and correspondence."""

    ENTITY = "document_register"
    FIELDS = [
        "reference",
        "status",
        "document_number",
        "title",
        "document_type",
        "revision",
        "source_document",
        "checksum",
        "issued_date",
        "supersedes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "document_number": {"required": True, "type": "str"},
        "title": {"type": "str"},
        "document_type": {
            "type": "str",
            "allowed_values": ["contract", "boq", "drawing", "correspondence", "itp", "certificate"],
        },
        "revision": {"type": "str"},
        "source_document": {"type": "str", "allowed_values": SOURCE_DOCUMENTS},
        "checksum": {"type": "str"},
        "issued_date": {"type": "date"},
        "supersedes": {"type": "str"},
    }
    reference: str = ""
    status: str = "open"
    document_number: str = ""
    title: str = ""
    document_type: str = ""
    revision: str = ""
    source_document: str = ""
    checksum: str = ""
    issued_date: Optional[_dt.date] = None
    supersedes: str = ""


class RetentionDefectsRelease(Model):
    """Retention release schedule and performance-security obligation.

    Retention is 5% of each certificate, released 50% at Taking-Over and 50%
    at the end of the 365-day Defects Notification Period (Clauses 14.3 and
    11.1); the performance security is 10% of the Accepted Contract Amount
    (Clause 4.2).
    """

    ENTITY = "retention_defects_release"
    FIELDS = [
        "reference",
        "status",
        "certificate_reference",
        "gross_certified_amount",
        "taking_over_date",
        "defects_notification_end_date",
        "release_stage",
        "approval_decision",
        "approved_by",
        "performance_security_amount",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "certificate_reference": {"required": True, "type": "str"},
        "gross_certified_amount": {"type": "float", "min": 0},
        "taking_over_date": {"type": "date"},
        "defects_notification_end_date": {"type": "date"},
        "release_stage": {
            "type": "str",
            "allowed_values": ["taking_over", "defects_end", "final"],
        },
        "approval_decision": {"type": "str", "allowed_values": ["none", "release", "hold"]},
        "approved_by": {"type": "str", "approval": True},
        "performance_security_amount": {"type": "float", "min": 0},
    }
    reference: str = ""
    status: str = "open"
    certificate_reference: str = ""
    gross_certified_amount: float = 0.0
    taking_over_date: Optional[_dt.date] = None
    defects_notification_end_date: Optional[_dt.date] = None
    release_stage: str = ""
    approval_decision: str = "none"
    approved_by: str = ""
    performance_security_amount: float = 0.0


class ContractVerification(Model):
    """Grounding check: every record must cite a governing clause or BOQ item."""

    ENTITY = "contract_verification_gate"
    FIELDS = [
        "reference",
        "status",
        "subject_type",
        "subject_reference",
        "clause_ref",
        "boq_item_code",
        "evidence",
        "decision",
    ]
    CONSTRAINTS = {
        "reference": {"required": True, "type": "str"},
        "status": {"type": "str", "allowed_values": ENVELOPE_STATUS},
        "subject_type": {
            "type": "str",
            "allowed_values": ["claim", "certificate", "itp", "document", "other"],
        },
        "subject_reference": {"required": True, "type": "str"},
        "clause_ref": {"type": "str", "allowed_values": CLAUSE_REFS},
        "boq_item_code": {"type": "str", "allowed_values": BOQ_ITEM_CODES},
        "evidence": {"type": "str"},
        "decision": {"type": "str", "allowed_values": ["verify", "flag", "refuse"]},
    }
    reference: str = ""
    status: str = "open"
    subject_type: str = ""
    subject_reference: str = ""
    clause_ref: str = ""
    boq_item_code: str = ""
    evidence: str = ""
    decision: str = "verify"


MODELS = {
    ProgressClaim.ENTITY: ProgressClaim,
    DelayDamagesAssessment.ENTITY: DelayDamagesAssessment,
    QAItpRecord.ENTITY: QAItpRecord,
    DocumentRegisterEntry.ENTITY: DocumentRegisterEntry,
    RetentionDefectsRelease.ENTITY: RetentionDefectsRelease,
    ContractVerification.ENTITY: ContractVerification,
}

CAPABILITY_IDS = list(MODELS)


def model_for(capability_id: str):
    return MODELS.get(str(capability_id))


def entity_for(capability_id: str) -> str:
    cls = model_for(capability_id)
    return getattr(cls, "ENTITY", str(capability_id).replace("-", "_"))
