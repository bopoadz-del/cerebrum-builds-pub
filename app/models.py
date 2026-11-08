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
TERM_TYPES = [str(row.get("key") or "") for row in sources.CLAUSES]
BOQ_ITEM_CODES = [str(row.get("item") or "") for row in sources.BOQ_ITEMS]
TEST_RESULTS = ["pass", "fail", "pending"]
SOURCE_DOCUMENTS = [CONTRACT_DOCUMENT, BOQ_DOCUMENT]


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


class ProgressClaimManagement(EntityModel):
    """An interim payment certificate measured against a BOQ line.

    Retention and performance security are deducted at the percentages the
    uploaded contract states; the claim is routed through reconciliation and
    approval before it is certified.
    """

    CAPABILITY_ID = "progress_claim_management"
    ENTITY = "progress_claim_management"
    FIELDS = [
        "reference",
        "boq_item",
        "description",
        "period",
        "claimed_quantity",
        "rate",
        "gross_amount",
        "accepted_contract_amount",
        "retention_pct",
        "ipc_number",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES)},
            "description": {"type": "str", "max_length": 500},
            "period": {"type": "str", "max_length": 120},
            "claimed_quantity": {"type": "quantity", "min": 0},
            "rate": {"type": "money", "min": 0},
            "gross_amount": {"type": "money", "min": 0},
            "accepted_contract_amount": {"type": "money", "min": 0},
            "retention_pct": {"type": "float", "min": 0, "max": 100},
            "ipc_number": {"type": "str", "max_length": 80},
        }
    )
    MONEY_FIELDS = ("rate", "gross_amount", "accepted_contract_amount")
    QUANTITY_FIELDS = ("claimed_quantity",)

    reference: str = ""
    boq_item: str = ""
    description: str = ""
    period: str = ""
    claimed_quantity: Optional[float] = None
    rate: Optional[float] = None
    gross_amount: Optional[float] = None
    accepted_contract_amount: Optional[float] = None
    retention_pct: Optional[float] = None
    ipc_number: str = ""
    status: str = "open"


class DelayDamagesTracking(EntityModel):
    """Elapsed time against the Time for Completion and delay-damages exposure.

    ``delay_days`` is measured from the Commencement Date when one is given,
    otherwise the caller may state it. Damages are the daily percentage of
    the Accepted Contract Amount, capped at the contractual percentage; the
    record reports when the cap is reached.
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
    A defect stays open for the defects-notification period the contract
    states.
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


class ContractTermsGovernance(EntityModel):
    """A governing contract term, its clause citation and compliance check.

    The term is registered against the uploaded contract excerpt. A caller
    value that diverges from the contract is reported as a divergence, and
    the term is submitted to the governance gate before it can be relied on.
    """

    CAPABILITY_ID = "contract_terms_governance"
    ENTITY = "contract_terms_governance"
    FIELDS = [
        "reference",
        "term_type",
        "value",
        "unit",
        "source_document",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "term_type": {
                "type": "str",
                "allowed_values": list(TERM_TYPES),
                "required": True,
            },
            "value": {"type": "float", "min": 0},
            "unit": {"type": "str", "max_length": 60},
            "source_document": {
                "type": "str",
                "allowed_values": list(SOURCE_DOCUMENTS),
            },
        }
    )

    reference: str = ""
    term_type: str = ""
    value: Optional[float] = None
    unit: str = ""
    source_document: str = ""
    status: str = "open"


class CommercialDashboard(EntityModel):
    """The project's commercial position, aggregated from stored records.

    Claims by status, certified totals, retention held, delay exposure and
    outstanding inspection items. Totals come from the tenant's own rows or
    from the snapshot the caller supplies; nothing is invented.
    """

    CAPABILITY_ID = "commercial_dashboard"
    ENTITY = "commercial_dashboard"
    FIELDS = [
        "reference",
        "period",
        "claim_status",
        "cumulative_certified",
        "retention_balance",
        "delay_exposure",
        "qa_open_items",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "period": {"type": "str", "max_length": 120},
            "claim_status": {
                "type": "str",
                "allowed_values": list(STATUS_VALUES),
            },
            "cumulative_certified": {"type": "money", "min": 0},
            "retention_balance": {"type": "money", "min": 0},
            "delay_exposure": {"type": "money", "min": 0},
            "qa_open_items": {"type": "int", "min": 0},
        }
    )
    MONEY_FIELDS = ("cumulative_certified", "retention_balance", "delay_exposure")

    reference: str = ""
    period: str = ""
    claim_status: str = "open"
    cumulative_certified: Optional[float] = None
    retention_balance: Optional[float] = None
    delay_exposure: Optional[float] = None
    qa_open_items: Optional[int] = None
    status: str = "open"


MODELS: Dict[str, type] = {
    ProgressClaimManagement.CAPABILITY_ID: ProgressClaimManagement,
    DelayDamagesTracking.CAPABILITY_ID: DelayDamagesTracking,
    QaItpRecords.CAPABILITY_ID: QaItpRecords,
    DocumentRegister.CAPABILITY_ID: DocumentRegister,
    ContractTermsGovernance.CAPABILITY_ID: ContractTermsGovernance,
    CommercialDashboard.CAPABILITY_ID: CommercialDashboard,
}
