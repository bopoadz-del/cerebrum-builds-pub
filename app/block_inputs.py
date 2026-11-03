"""Constructed block inputs and the default action of each bound block.

A caller never has to know a block's own keys (topic, steps, sql, file
paths): the capability handler constructs them from the domain record.
These defaults are read from each bound block's declared action.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

DEFAULT_ACTIONS: Dict[str, Optional[str]] = {
    "analytics": "track_event",
    "approval_rules": "ingest",
    "audit": "log",
    "audit_chain": "record_evidence",
    "construction_advisor": None,
    "cpm_engine": "compute",
    "dashboard": "render",
    "document_engine": None,
    "estate_maintenance": "create",
    "evidence_chain": "verify",
    "evidence_classifier": "classify",
    "evidence_or_refuse": "judge",
    "evidence_verifier": "store",
    "finance_reconciliation": None,
    "finance_reconciliation_workflow": "create_run",
    "formula_executor": None,
    "governance_gate": "require_approved",
    "ingestion_provenance": "build",
    "notification": "send",
    "search": None,
    "storage": "store",
    "validation": "validate_pipeline",
    "version_diff": "diff",
    "workflow": "run",
}


def default_block_action(block_id: str) -> Optional[str]:
    return DEFAULT_ACTIONS.get(str(block_id))


def prepare_block_input(capability_id: str, block_id: str,
                        record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A minimal, valid input for a block, built from the domain record.

    Never forwards the raw request: the block's own keys are synthesized
    here (a workflow gets steps, an event gets topic/payload/message).
    """
    record = dict(record or {})
    reference = str(record.get("reference") or "sample")
    if block_id == "workflow":
        return {
            "pipeline_id": f"{capability_id}-{reference}",
            "steps": [
                {
                    "id": "step_0",
                    "block": "validation",
                    "input": {"pipeline": {"id": capability_id, "type": "pipeline"}},
                    "action": default_block_action("validation"),
                }
            ],
        }
    if block_id == "event_bus":
        return {
            "topic": f"{capability_id}.{str(record.get('status') or 'open')}",
            "payload": {"reference": reference},
            "message": f"{capability_id} {reference}",
            "channel": "mcp",
            "tool": "event_bus",
        }
    if block_id == "validation":
        return {"pipeline": {"id": capability_id, "type": "pipeline"},
                "blocks": [capability_id]}
    if block_id in ("document_engine",):
        return {"text": str(record.get("title") or record.get("description") or reference)}
    if block_id in ("search",):
        return {"query": str(record.get("title") or record.get("boq_item") or reference)}
    if block_id in ("storage",):
        content = str(record.get("checksum") or record.get("title") or reference)
        return {"content": content, "filename": f"{reference}.txt"}
    if block_id in ("finance_reconciliation",):
        return {"left_records": [], "right_records": [], "group_by": ["account_id"]}
    return {"reference": reference, "record": record}
