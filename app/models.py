"""Capability models: what each capability declares it accepts.

Every model carries the platform envelope -- ``reference`` identifies the
record a caller is talking about, ``status`` is the schema-enforced
vocabulary ``open | in_progress | closed`` -- plus the domain fields that
capability actually reads and writes. The constraints here are the contract
the route enforces and the one the harness builds its probe payload from.

The source of record is the uploaded contract excerpt and BOQ, read from
``corpus/source_of_record.json`` through ``app.sources``. No clause number,
BOQ item code or document id is typed into this module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import sources

CONTRACT_DOCUMENT = sources.CONTRACT_DOCUMENT
BOQ_DOCUMENT = sources.BOQ_DOCUMENT

STATUS_VALUES = ["open", "in_progress", "closed"]

DOCUMENT_TYPES = ["contract", "boq"]
REGISTER_TYPES = [
    "contract",
    "boq",
    "drawing",
    "itp",
    "certificate",
    "report",
    "claim",
    "correspondence",
]
CLAUSE_REFS = sources.clause_numbers()
BOQ_ITEM_CODES = [str(row.get("item") or "") for row in sources.BOQ_ITEMS]
TEST_RESULTS = ["pass", "fail", "pending"]
SOURCE_DOCUMENTS = [CONTRACT_DOCUMENT, BOQ_DOCUMENT]
MILESTONES = ["taking_over", "defects_notification_end", "performance_security"]


class EntityModel:
    """The shared envelope and the persistence identity of one capability."""

    CAPABILITY_ID: str = ""
    ENTITY: str = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    MONEY_FIELDS: tuple = ()
    QUANTITY_FIELDS: tuple = ()

    id: Optional[int] = None
    tenant_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __init__(self, **values: Any) -> None:
        self.id = values.pop("id", None)
        self.tenant_id = values.pop("tenant_id", None)
        self.created_at = values.pop("created_at", None)
        self.updated_at = values.pop("updated_at", None)
        for name in self.FIELDS:
            setattr(self, name, values.get(name))

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "EntityModel":
        return cls(**(data or {}))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"id": self.id}
        for name in self.FIELDS:
            out[name] = getattr(self, name, None)
        out["tenant_id"] = self.tenant_id
        out["created_at"] = self.created_at
        out["updated_at"] = self.updated_at
        return out

    @classmethod
    def sample(cls) -> Dict[str, Any]:
        from app.validation import sample_for_model

        return sample_for_model(cls)


def _envelope(extra: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {
        "reference": {"type": "str", "required": True, "max_length": 200},
        "status": {
            "type": "str",
            "allowed_values": list(STATUS_VALUES),
            "required": False,
        },
    }
    out.update(extra)
    return out


class ContractAndBoqSourceOfRecord(EntityModel):
    """A governing term held as the immutable source of record.

    One record resolves either a contract clause or a BOQ line, cites the
    uploaded document it comes from, and reports the derived amount for a
    BOQ quantity at its rate.
    """

    CAPABILITY_ID = "contract_and_boq_source_of_record"
    ENTITY = "contract_and_boq_source_of_record"
    FIELDS = [
        "reference",
        "document_type",
        "source_document",
        "clause_ref",
        "boq_item",
        "description",
        "unit",
        "quantity",
        "rate",
        "amount",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "document_type": {
                "type": "str",
                "allowed_values": list(DOCUMENT_TYPES),
                "required": True,
            },
            "source_document": {
                "type": "str",
                "allowed_values": list(SOURCE_DOCUMENTS),
            },
            "clause_ref": {"type": "str", "allowed_values": list(CLAUSE_REFS)},
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES)},
            "description": {"type": "str", "max_length": 500},
            "unit": {"type": "str", "max_length": 60},
            "quantity": {"type": "quantity", "min": 0},
            "rate": {"type": "money", "min": 0},
            "amount": {"type": "money", "min": 0},
        }
    )
    MONEY_FIELDS = ("rate", "amount")
    QUANTITY_FIELDS = ("quantity",)

    reference: str = ""
    document_type: str = ""
    source_document: str = ""
    clause_ref: str = ""
    boq_item: str = ""
    description: str = ""
    unit: str = ""
    quantity: Optional[float] = None
    rate: Optional[float] = None
    amount: Optional[float] = None
    status: str = "open"


class ProgressClaimsAndPaymentCertificates(EntityModel):
    """An Interim Payment Certificate measured against a BOQ line.

    Retention follows Clause 14.3 (5% of each certificate, released 50% at
    Taking-Over and 50% at the end of the Defects Notification Period); the
    performance security follows Clause 4.2, and the certificate is routed
    through approval before it is certified.
    """

    CAPABILITY_ID = "progress_claims_and_payment_certificates"
    ENTITY = "progress_claims_and_payment_certificates"
    FIELDS = [
        "reference",
        "boq_item",
        "period",
        "claimed_quantity",
        "gross_amount",
        "accepted_contract_amount",
        "retention_pct",
        "ipc_number",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES)},
            "period": {"type": "str", "max_length": 120},
            "claimed_quantity": {"type": "quantity", "min": 0},
            "gross_amount": {"type": "money", "min": 0},
            "accepted_contract_amount": {"type": "money", "min": 0},
            "retention_pct": {"type": "float", "min": 0, "max": 100},
            "ipc_number": {"type": "str", "max_length": 80},
        }
    )
    MONEY_FIELDS = ("gross_amount", "accepted_contract_amount")
    QUANTITY_FIELDS = ("claimed_quantity",)

    reference: str = ""
    boq_item: str = ""
    period: str = ""
    claimed_quantity: Optional[float] = None
    gross_amount: Optional[float] = None
    accepted_contract_amount: Optional[float] = None
    retention_pct: Optional[float] = None
    ipc_number: str = ""
    status: str = "open"


class DelayDamagesTracking(EntityModel):
    """Elapsed time against the Time for Completion and Clause 8.7 exposure.

    ``delay_days`` is measured from the Commencement Date when one is given,
    otherwise the caller may state it. Damages are 0.1% of the Accepted
    Contract Amount per day, capped at 10%; the record reports when the cap
    is reached and carries the evidence for an extension-of-time position.
    """

    CAPABILITY_ID = "delay_damages_tracking"
    ENTITY = "delay_damages_tracking"
    FIELDS = [
        "reference",
        "commencement_date",
        "assessment_date",
        "accepted_contract_amount",
        "daily_rate_pct",
        "cap_pct",
        "delay_days",
        "extension_days",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "commencement_date": {"type": "date", "format": "date"},
            "assessment_date": {"type": "date", "format": "date"},
            "accepted_contract_amount": {"type": "money", "min": 0},
            "daily_rate_pct": {"type": "float", "min": 0, "max": 100},
            "cap_pct": {"type": "float", "min": 0, "max": 100},
            "delay_days": {"type": "int", "min": 0},
            "extension_days": {"type": "int", "min": 0},
        }
    )
    MONEY_FIELDS = ("accepted_contract_amount",)

    reference: str = ""
    commencement_date: Optional[str] = None
    assessment_date: Optional[str] = None
    accepted_contract_amount: Optional[float] = None
    daily_rate_pct: Optional[float] = None
    cap_pct: Optional[float] = None
    delay_days: Optional[int] = None
    extension_days: Optional[int] = None
    status: str = "open"


class QaItpRecords(EntityModel):
    """An Inspection and Test Plan record for one inspection lot.

    Records the BOQ item covered, hold and witness points, the test verdict
    and sign-off. A lot is accepted only when the test result is ``pass``.
    Defects stay open through the Defects Notification Period (365 days from
    Taking-Over, Clause 11.1).
    """

    CAPABILITY_ID = "qa_itp_records"
    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference",
        "boq_item",
        "inspection_lot",
        "inspection_date",
        "test_result",
        "hold_point",
        "witness_point",
        "defect_ref",
        "defect_close_out_date",
        "signoff_by",
        "taking_over_date",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES)},
            "inspection_lot": {"type": "str", "max_length": 120},
            "inspection_date": {"type": "date", "format": "date"},
            "test_result": {
                "type": "str",
                "allowed_values": list(TEST_RESULTS),
            },
            "hold_point": {"type": "str", "max_length": 200},
            "witness_point": {"type": "str", "max_length": 200},
            "defect_ref": {"type": "str", "max_length": 120},
            "defect_close_out_date": {"type": "date", "format": "date"},
            "signoff_by": {"type": "str", "max_length": 120},
            "taking_over_date": {"type": "date", "format": "date"},
        }
    )

    reference: str = ""
    boq_item: str = ""
    inspection_lot: str = ""
    inspection_date: Optional[str] = None
    test_result: str = "pending"
    hold_point: str = ""
    witness_point: str = ""
    defect_ref: str = ""
    defect_close_out_date: Optional[str] = None
    signoff_by: str = ""
    taking_over_date: Optional[str] = None
    status: str = "open"


class DocumentRegister(EntityModel):
    """A controlled project document with revision control and provenance.

    A register entry pins a document to the source document it belongs to, so
    a claim, an ITP record or a certificate cites the controlled revision
    rather than a loose copy.
    """

    CAPABILITY_ID = "document_register"
    ENTITY = "document_register"
    FIELDS = [
        "reference",
        "title",
        "document_type",
        "revision",
        "source_document",
        "revision_date",
        "checksum",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "title": {"type": "str", "max_length": 300},
            "document_type": {
                "type": "str",
                "allowed_values": list(REGISTER_TYPES),
                "required": True,
            },
            "revision": {"type": "str", "max_length": 60},
            "source_document": {"type": "str", "max_length": 500},
            "revision_date": {"type": "date", "format": "date"},
            "checksum": {"type": "str", "max_length": 128},
        }
    )

    reference: str = ""
    title: str = ""
    document_type: str = "contract"
    revision: str = ""
    source_document: str = ""
    revision_date: Optional[str] = None
    checksum: str = ""
    status: str = "open"


class ClaimReviewAndDisputeResolution(EntityModel):
    """A reviewed claim and, where the parties disagree, its determination.

    Reviews a submitted claim against the source of record, records the
    disputed item and the basis of the determination, and keeps the evidence
    trail. A determination above the claimed value, or one without a basis,
    is refused rather than recorded.
    """

    CAPABILITY_ID = "claim_review_and_dispute_resolution"
    ENTITY = "claim_review_and_dispute_resolution"
    FIELDS = [
        "reference",
        "claim_reference",
        "disputed_item",
        "claimed_value",
        "determined_value",
        "basis",
        "determination",
        "reviewer",
        "evidence_ref",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "claim_reference": {"type": "str", "max_length": 200},
            "disputed_item": {"type": "str", "max_length": 200},
            "claimed_value": {"type": "money", "min": 0},
            "determined_value": {"type": "money", "min": 0},
            "basis": {"type": "str", "max_length": 500},
            "determination": {
                "type": "str",
                "allowed_values": ["accepted", "reduced", "rejected", "pending"],
            },
            "reviewer": {"type": "str", "max_length": 120},
            "evidence_ref": {"type": "str", "max_length": 200},
        }
    )
    MONEY_FIELDS = ("claimed_value", "determined_value")

    reference: str = ""
    claim_reference: str = ""
    disputed_item: str = ""
    claimed_value: Optional[float] = None
    determined_value: Optional[float] = None
    basis: str = ""
    determination: str = "pending"
    reviewer: str = ""
    evidence_ref: str = ""
    status: str = "open"


MODELS: Dict[str, type] = {
    ContractAndBoqSourceOfRecord.CAPABILITY_ID: ContractAndBoqSourceOfRecord,
    ProgressClaimsAndPaymentCertificates.CAPABILITY_ID: ProgressClaimsAndPaymentCertificates,
    DelayDamagesTracking.CAPABILITY_ID: DelayDamagesTracking,
    QaItpRecords.CAPABILITY_ID: QaItpRecords,
    DocumentRegister.CAPABILITY_ID: DocumentRegister,
    ClaimReviewAndDisputeResolution.CAPABILITY_ID: ClaimReviewAndDisputeResolution,
}
