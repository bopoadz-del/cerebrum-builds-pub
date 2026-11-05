"""Capability models: what each capability declares it accepts.

Every model carries the platform envelope -- ``reference`` identifies the
record a caller is talking about, ``status`` is the schema-enforced
vocabulary ``open | in_progress | closed`` -- plus the domain fields that
capability actually reads and writes. The constraints here are the contract
the route enforces and the one the harness builds its probe payload from.

The product is a contracts-administration platform for Harbourline Civil
Works. Its source of record is the uploaded contract excerpt and BOQ:
``document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf`` and
``document:9eef45a732d042dfb83157ec67068a75_harbourline_boq.xlsx``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.config import BOQ_DOCUMENT, CONTRACT_DOCUMENT

STATUS_VALUES = ["open", "in_progress", "closed"]

DOCUMENT_TYPES = ["contract", "boq"]
CLAUSE_REFS = ["4.2", "8.2", "8.7", "11.1", "14.3"]
BOQ_ITEM_CODES = ["P1", "P2", "P3", "P4", "P5", "E1", "E2", "E3", "E4", "E5"]
REGISTER_TYPES = ["contract", "boq", "drawing", "report", "certificate"]
TEST_RESULTS = ["pass", "fail", "pending"]
ROLES = ["owner", "contracts_manager", "quantity_surveyor", "viewer"]
PERMISSIONS = ["contract.read", "contract.write", "claim.submit", "claim.approve", "document.publish", "audit.read"]
ACTIONS = ["read", "write", "approve", "export"]
DECISIONS = ["allow", "deny"]


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
        return out

    @classmethod
    def sample(cls) -> Dict[str, Any]:
        from app.validation import sample_for_model

        return sample_for_model(cls)


def _envelope(extra: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {
        "reference": {"type": "str", "required": True, "max_length": 200},
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": False},
    }
    out.update(extra)
    return out


class ContractSourceOfRecord(EntityModel):
    """The contract excerpt and BOQ line held as the single source of record.

    A record pins one clause or BOQ line to the document it came from, so a
    later claim, inspection or certificate can cite ``document:<filename>``
    instead of restating (or inventing) a rate.
    """

    CAPABILITY_ID = "contract_source_of_record"
    ENTITY = "contract_source_of_record"
    FIELDS = [
        "reference",
        "source_document",
        "document_type",
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
            "source_document": {"type": "str", "allowed_values": [CONTRACT_DOCUMENT, BOQ_DOCUMENT], "max_length": 500},
            "document_type": {"type": "str", "allowed_values": list(DOCUMENT_TYPES)},
            "clause_ref": {"type": "str", "allowed_values": list(CLAUSE_REFS), "max_length": 40},
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES), "max_length": 40},
            "description": {"type": "str", "max_length": 1000},
            "unit": {"type": "str", "max_length": 20},
            "quantity": {"type": "float", "min": 0},
            "rate": {"type": "float", "min": 0},
            "amount": {"type": "float", "min": 0},
        }
    )
    MONEY_FIELDS = ("rate", "amount")
    QUANTITY_FIELDS = ("quantity",)

    reference: str = ""
    source_document: str = ""
    document_type: str = ""
    clause_ref: str = ""
    boq_item: str = ""
    description: str = ""
    unit: str = ""
    quantity: float = 0.0
    rate: float = 0.0
    amount: float = 0.0
    status: str = "open"


class ProgressClaims(EntityModel):
    """Interim Payment Certificate under Clauses 14.3 and 4.2.

    Gross value of the certified BOQ quantity less 5% retention (Clause 14.3)
    and the performance-security deduction (Clause 4.2), with the 50/50
    retention release points stated on the certificate.
    """

    CAPABILITY_ID = "progress_claims"
    ENTITY = "progress_claims"
    FIELDS = [
        "reference",
        "ipc_number",
        "boq_item",
        "period",
        "gross_amount",
        "accepted_contract_amount",
        "retention_pct",
        "retention_amount",
        "performance_security_rate",
        "performance_security_deduction",
        "net_certified",
        "currency",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "ipc_number": {"type": "str", "max_length": 40},
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES), "max_length": 40},
            "period": {"type": "str", "max_length": 40},
            "gross_amount": {"type": "float", "min": 0},
            "accepted_contract_amount": {"type": "float", "min": 0},
            "retention_pct": {"type": "float", "min": 0, "max": 100},
            "retention_amount": {"type": "float", "min": 0},
            "performance_security_rate": {"type": "float", "min": 0, "max": 100},
            "performance_security_deduction": {"type": "float", "min": 0},
            "net_certified": {"type": "float", "min": 0},
            "currency": {"type": "str", "max_length": 8},
        }
    )
    MONEY_FIELDS = (
        "gross_amount",
        "accepted_contract_amount",
        "retention_amount",
        "performance_security_deduction",
        "net_certified",
    )

    reference: str = ""
    ipc_number: str = ""
    boq_item: str = ""
    period: str = ""
    gross_amount: float = 0.0
    accepted_contract_amount: float = 0.0
    retention_pct: float = 5.0
    retention_amount: float = 0.0
    performance_security_rate: float = 10.0
    performance_security_deduction: float = 0.0
    net_certified: float = 0.0
    currency: str = "SAR"
    status: str = "open"


class TimeAndDelayDamages(EntityModel):
    """Time for Completion and delay-damages exposure under Clauses 8.2/8.7.

    730 days from commencement, 0.1% of the Accepted Contract Amount per day
    of delay, capped at 10% of the Accepted Contract Amount.
    """

    CAPABILITY_ID = "time_and_delay_damages"
    ENTITY = "time_and_delay_damages"
    FIELDS = [
        "reference",
        "commencement_date",
        "completion_date",
        "time_for_completion_days",
        "accepted_contract_amount",
        "delay_days",
        "delay_damages_rate_pct",
        "delay_damages",
        "damages_cap_pct",
        "cap_reached",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "commencement_date": {"type": "str", "format": "date"},
            "completion_date": {"type": "str", "format": "date"},
            "time_for_completion_days": {"type": "int", "min": 1},
            "accepted_contract_amount": {"type": "float", "min": 0},
            "delay_days": {"type": "int", "min": 0},
            "delay_damages_rate_pct": {"type": "float", "min": 0, "max": 100},
            "delay_damages": {"type": "float", "min": 0},
            "damages_cap_pct": {"type": "float", "min": 0, "max": 100},
            "cap_reached": {"type": "bool"},
        }
    )
    MONEY_FIELDS = ("accepted_contract_amount", "delay_damages")

    reference: str = ""
    commencement_date: date = date(2026, 9, 3)
    completion_date: date = date(2026, 9, 3)
    time_for_completion_days: int = 730
    accepted_contract_amount: float = 0.0
    delay_days: int = 0
    delay_damages_rate_pct: float = 0.1
    delay_damages: float = 0.0
    damages_cap_pct: float = 10.0
    cap_reached: bool = False
    status: str = "open"


class QaItpRecords(EntityModel):
    """QA/ITP inspection record tied to one BOQ item and inspection lot."""

    CAPABILITY_ID = "qa_itp_records"
    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference",
        "boq_item",
        "inspection_lot",
        "hold_point",
        "witness_point",
        "test_result",
        "inspection_date",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "boq_item": {"type": "str", "allowed_values": list(BOQ_ITEM_CODES), "max_length": 40},
            "inspection_lot": {"type": "str", "max_length": 80},
            "hold_point": {"type": "str", "max_length": 200},
            "witness_point": {"type": "str", "max_length": 200},
            "test_result": {"type": "str", "allowed_values": list(TEST_RESULTS)},
            "inspection_date": {"type": "str", "format": "date"},
        }
    )

    reference: str = ""
    boq_item: str = ""
    inspection_lot: str = ""
    hold_point: str = ""
    witness_point: str = ""
    test_result: str = "pending"
    inspection_date: date = date(2026, 9, 3)
    status: str = "open"


class DocumentRegister(EntityModel):
    """Controlled document register with revision, checksum and provenance."""

    CAPABILITY_ID = "document_register"
    ENTITY = "document_register"
    FIELDS = [
        "reference",
        "title",
        "document_type",
        "revision",
        "checksum",
        "source_document",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "title": {"type": "str", "max_length": 300},
            "document_type": {"type": "str", "allowed_values": list(REGISTER_TYPES)},
            "revision": {"type": "str", "max_length": 40},
            "checksum": {"type": "str", "max_length": 128},
            "source_document": {"type": "str", "max_length": 500},
        }
    )

    reference: str = ""
    title: str = ""
    document_type: str = "contract"
    revision: str = ""
    checksum: str = ""
    source_document: str = ""
    status: str = "open"


class RoleBasedAccessAndAudit(EntityModel):
    """A role/permission decision recorded in the fail-closed audit ledger."""

    CAPABILITY_ID = "role_based_access_and_audit"
    ENTITY = "role_based_access_and_audit"
    FIELDS = [
        "reference",
        "principal_id",
        "role",
        "permission",
        "requested_action",
        "decision",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "principal_id": {"type": "str", "max_length": 120},
            "role": {"type": "str", "allowed_values": list(ROLES)},
            "permission": {"type": "str", "allowed_values": list(PERMISSIONS)},
            "requested_action": {"type": "str", "allowed_values": list(ACTIONS)},
            "decision": {"type": "str", "allowed_values": list(DECISIONS)},
        }
    )

    reference: str = ""
    principal_id: str = ""
    role: str = "viewer"
    permission: str = "contract.read"
    requested_action: str = "read"
    decision: str = "allow"
    status: str = "open"


MODELS: Dict[str, Any] = {
    ContractSourceOfRecord.CAPABILITY_ID: ContractSourceOfRecord,
    ProgressClaims.CAPABILITY_ID: ProgressClaims,
    TimeAndDelayDamages.CAPABILITY_ID: TimeAndDelayDamages,
    QaItpRecords.CAPABILITY_ID: QaItpRecords,
    DocumentRegister.CAPABILITY_ID: DocumentRegister,
    RoleBasedAccessAndAudit.CAPABILITY_ID: RoleBasedAccessAndAudit,
}

CAPABILITY_IDS: List[str] = list(MODELS)


def model_for(capability_id: str):
    return MODELS.get(str(capability_id or ""))


def entity_for(capability_id: str) -> str:
    cls = model_for(capability_id)
    if cls is None:
        raise KeyError(f"unknown capability: {capability_id}")
    return cls.ENTITY or cls.CAPABILITY_ID.replace("-", "_")
