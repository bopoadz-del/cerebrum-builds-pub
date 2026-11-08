"""Domain models for the the project contracts platform.

Every capability carries the platform envelope ``reference`` + ``status``;
the status vocabulary is schema-enforced here (open | in_progress | closed)
by ``CONSTRAINTS.allowed_values``, never described in prose.

Persistence: ``ENTITY`` is the capability id -- the table
alembic/versions/0001_baseline.py creates and the name app/store.py uses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ENVELOPE_STATUS = ["open", "in_progress", "closed"]

DOCUMENT_CONTRACT = (
    "document:32f1c3b59a814857ba7afb4de62261da_harbourline_contract.pdf"
)
DOCUMENT_BOQ = (
    "document:a869a19e66cf48e3bfe4c64fad2ed2ac_harbourline_boq.xlsx"
)


def _rules(type_name: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"type": type_name}
    out.update(extra)
    return out


class DomainModel:
    """Plain, offline record model: declared fields plus a mapping contract."""

    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    MONEY_FIELDS: List[str] = []
    ENTITY = ""

    def __init__(self, **values: Any) -> None:
        self.id: Optional[int] = None
        for name in self.FIELDS:
            if name in values:
                value = values[name]
            else:
                kind = (self.CONSTRAINTS.get(name) or {}).get("type")
                value = (
                    False if kind == "bool"
                    else 0 if kind == "int"
                    else 0.0 if kind == "float"
                    else ""
                )
            setattr(self, name, value)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DomainModel":
        record = cls()
        source = data or {}
        for name in cls.FIELDS:
            if name in source:
                setattr(record, name, source[name])
        if isinstance(source.get("id"), int):
            record.id = source["id"]
        return record

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"id": self.id}
        for name in self.FIELDS:
            out[name] = getattr(self, name, None)
        return out


_ENVELOPE = {
    "reference": _rules("str", required=True, min_length=1),
    "status": _rules("str", required=True, allowed_values=list(ENVELOPE_STATUS)),
}


class SourceRecord(DomainModel):
    """The contract and BOQ as the project's authoritative source of record."""

    reference: str
    status: str
    document_ref: str
    document_kind: str
    clause_ref: str
    clause_title: str
    pinned_value: str
    version: str
    effective_date: str
    source_digest: str

    ENTITY = "contract_source_of_record"
    FIELDS = [
        "reference", "status", "document_ref", "document_kind", "clause_ref",
        "clause_title", "pinned_value", "version", "effective_date",
        "source_digest",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "document_ref": _rules("str", format="identifier"),
        "document_kind": _rules("str", allowed_values=["contract", "boq"]),
        "clause_ref": _rules("str"),
        "clause_title": _rules("str"),
        "pinned_value": _rules("str"),
        "version": _rules("str"),
        "effective_date": _rules("str", format="date"),
        "source_digest": _rules("str"),
    }


class ProgressClaim(DomainModel):
    """An Interim Payment Certificate measured against BOQ items."""

    reference: str
    status: str
    ipc_number: str
    period: str
    boq_item: str
    measured_quantity: float
    unit_rate: float
    retention_percent: float
    taking_over: bool
    defects_notified: bool
    certified_amount: float
    notes: str

    ENTITY = "progress_claims"
    FIELDS = [
        "reference", "status", "ipc_number", "period", "boq_item",
        "measured_quantity", "unit_rate", "retention_percent", "taking_over",
        "defects_notified", "certified_amount", "notes",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "ipc_number": _rules("str"),
        "period": _rules("str"),
        "boq_item": _rules("str"),
        "measured_quantity": _rules("float", min=0),
        "unit_rate": _rules("float", min=0),
        "retention_percent": _rules("float", min=0, max=100),
        "taking_over": _rules("bool"),
        "defects_notified": _rules("bool"),
        "certified_amount": _rules("float", min=0, format="money"),
        "notes": _rules("str"),
    }
    MONEY_FIELDS = ["certified_amount"]


class DelayDamages(DomainModel):
    """Time for Completion and delay-damages exposure for the project."""

    reference: str
    status: str
    commencement_date: str
    as_of_date: str
    accepted_contract_amount: float
    extension_days: int
    daily_rate_percent: float
    cap_percent: float
    taking_over: bool
    notify_channel: str
    notes: str

    ENTITY = "delay_damages_tracking"
    FIELDS = [
        "reference", "status", "commencement_date", "as_of_date",
        "accepted_contract_amount", "extension_days", "daily_rate_percent",
        "cap_percent", "taking_over", "notify_channel", "notes",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "commencement_date": _rules("str", format="date"),
        "as_of_date": _rules("str", format="date"),
        "accepted_contract_amount": _rules("float", min=0, format="money"),
        "extension_days": _rules("int", min=0),
        "daily_rate_percent": _rules("float", min=0, max=100),
        "cap_percent": _rules("float", min=0, max=100),
        "taking_over": _rules("bool"),
        "notify_channel": _rules("str", allowed_values=["mcp"]),
        "notes": _rules("str"),
    }
    MONEY_FIELDS = ["accepted_contract_amount"]


class QaItpRecord(DomainModel):
    """An Inspection and Test Plan record against a BOQ work item."""

    reference: str
    status: str
    itp_number: str
    boq_item: str
    inspection_type: str
    hold_point: bool
    witness_point: bool
    inspection_date: str
    result: str
    evidence_ref: str
    signed_off_by: str
    notes: str

    ENTITY = "qa_itp_records"
    FIELDS = [
        "reference", "status", "itp_number", "boq_item", "inspection_type",
        "hold_point", "witness_point", "inspection_date", "result",
        "evidence_ref", "signed_off_by", "notes",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "itp_number": _rules("str"),
        "boq_item": _rules("str"),
        "inspection_type": _rules("str"),
        "hold_point": _rules("bool"),
        "witness_point": _rules("bool"),
        "inspection_date": _rules("str", format="date"),
        "result": _rules("str", allowed_values=["pass", "fail", "hold"]),
        "evidence_ref": _rules("str"),
        "signed_off_by": _rules("str"),
        "notes": _rules("str"),
    }


class DocumentRegisterEntry(DomainModel):
    """A project document, its revision and its provenance."""

    reference: str
    status: str
    document_number: str
    document_type: str
    title: str
    revision: str
    issued_by: str
    issued_date: str
    source_document: str
    checksum: str
    distribution: str

    ENTITY = "document_register"
    FIELDS = [
        "reference", "status", "document_number", "document_type", "title",
        "revision", "issued_by", "issued_date", "source_document", "checksum",
        "distribution",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "document_number": _rules("str"),
        "document_type": _rules(
            "str",
            allowed_values=[
                "contract", "boq", "drawing", "itp", "submittal",
                "correspondence",
            ],
        ),
        "title": _rules("str"),
        "revision": _rules("str"),
        "issued_by": _rules("str"),
        "issued_date": _rules("str", format="date"),
        "source_document": _rules("str", format="identifier"),
        "checksum": _rules("str"),
        "distribution": _rules("str"),
    }


class ComplianceGate(DomainModel):
    """A claim, notification or taking-over submission checked against the
    pinned contract clauses and the BOQ schedule."""

    reference: str
    status: str
    submission_ref: str
    submission_type: str
    clause_ref: str
    requirement: str
    proposed_value: str
    decision: str
    checked_by: str

    ENTITY = "contract_compliance_gate"
    FIELDS = [
        "reference", "status", "submission_ref", "submission_type",
        "clause_ref", "requirement", "proposed_value", "decision", "checked_by",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "submission_ref": _rules("str"),
        "submission_type": _rules(
            "str",
            allowed_values=["progress_claim", "notification", "taking_over"],
        ),
        "clause_ref": _rules("str"),
        "requirement": _rules("str"),
        "proposed_value": _rules("str"),
        "decision": _rules("str", allowed_values=["pass", "refuse", "escalate"]),
        "checked_by": _rules("str"),
    }


MODELS = {
    "contract_source_of_record": SourceRecord,
    "progress_claims": ProgressClaim,
    "delay_damages_tracking": DelayDamages,
    "qa_itp_records": QaItpRecord,
    "document_register": DocumentRegisterEntry,
    "contract_compliance_gate": ComplianceGate,
}
