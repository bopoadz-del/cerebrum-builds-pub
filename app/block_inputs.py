"""Constructing a block's input from a domain record.

A capability assigns a block, so it feeds it: the block-specific keys (a file
path, a topic, a notice body) are built here from the record the caller gave
us -- they are never demanded from the caller.

The default action per block is the block's own contract: what its
block.json/code dispatches on when the caller names none. A block whose code
reads no action (boq_processor's parse, pdf, finance_reconciliation) has None
and is called without one.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: block id -> the action the block itself defaults to, read from the block.
BLOCK_DEFAULT_ACTIONS: Dict[str, Optional[str]] = {
    "approval_rules": "ingest",
    "audit": "log",
    "audit_chain": "record_evidence",
    "boq_processor": "status",
    "cpm_engine": "compute",
    "document_engine": None,
    "evidence_chain": "record",
    "evidence_or_refuse": "judge",
    "file_hasher": "hash",
    "finance_planning": "create_budget",
    "finance_reconciliation": None,
    "finance_reconciliation_workflow": "create_run",
    "formula_executor": None,
    "governance_gate": "require_approved",
    "ingestion_provenance": "build",
    "notification": "send",
    "pdf": None,
    "transaction_state_machine": "transition",
    "validation": "validate_pipeline",
    "version": "publish_version",
}

#: How a record's own scalars travel into a block's payload.
_CARRIED = (
    "reference",
    "status",
    "claim_number",
    "claim_period",
    "boq_item_code",
    "measured_quantity",
    "unit_rate",
    "accepted_contract_amount",
    "assessment_number",
    "days_of_delay",
    "itp_number",
    "inspection_type",
    "hold_point",
    "result",
    "document_number",
    "document_type",
    "revision",
    "source_document",
    "certificate_reference",
    "gross_certified_amount",
    "release_stage",
    "subject_type",
    "subject_reference",
    "clause_ref",
    "decision",
)


def default_block_action(block_id: str) -> Optional[str]:
    return BLOCK_DEFAULT_ACTIONS.get(str(block_id))


def carried_scalars(record: Dict[str, Any]) -> Dict[str, Any]:
    """The record's own scalar values, ready to travel into a block payload."""
    out: Dict[str, Any] = {}
    for name in _CARRIED:
        value = (record or {}).get(name)
        if isinstance(value, (str, int, float, bool)):
            out[name] = value
    return out


def prepare_block_input(
    block_id: str, record: Dict[str, Any], **overrides: Any
) -> Dict[str, Any]:
    """A block input built from the domain record, plus the keys that block
    needs to do its job."""
    payload = carried_scalars(record)
    payload.setdefault("tenant_id", "harbourline")
    if block_id == "notification":
        payload.setdefault("channel", "mcp")
        payload.setdefault("block", "notification")
        payload.setdefault("tool", "contracts_platform")
        payload.setdefault(
            "message",
            f"{record.get('subject_type') or record.get('document_type') or 'record'} "
            f"{record.get('reference') or ''}".strip(),
        )
    if block_id == "audit":
        payload.setdefault("action", "recorded")
        payload.setdefault("resource_type", record.get("subject_type") or "record")
        payload.setdefault("resource_id", record.get("reference") or "")
        payload.setdefault("details", carried_scalars(record))
    if block_id == "evidence_chain":
        payload.setdefault("action_type", record.get("subject_type") or "record")
        payload.setdefault("principal_id", record.get("approved_by") or "operator")
        payload.setdefault("payload", carried_scalars(record))
    if block_id == "audit_chain":
        payload.setdefault(
            "action_execution_id", record.get("reference") or record.get("subject_reference") or "record"
        )
        payload.setdefault("action_type", record.get("subject_type") or "record")
        payload.setdefault("principal_id", record.get("approved_by") or "operator")
    if block_id == "ingestion_provenance":
        payload.setdefault(
            "source",
            {
                "name": record.get("source_document") or record.get("reference") or "document",
                "kind": record.get("document_type") or "document",
            },
        )
    payload.update(overrides)
    return payload


def event_bus_step(
    topic: str, record: Dict[str, Any], message: str
) -> Dict[str, Any]:
    """A prepared event_bus workflow step.

    Every child a workflow runs must be ready before it starts: topic,
    payload, message, channel and tool are all constructed here from the
    domain record, never forwarded from the caller's payload.
    """
    return {
        "block": "event_bus",
        "action": "publish",
        "input": {
            "topic": str(topic or "contracts.record"),
            "payload": carried_scalars(record),
            "message": str(message or "contracts event"),
            "channel": "mcp",
            "tool": "event_bus",
        },
    }
