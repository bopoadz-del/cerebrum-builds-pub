"""contract_terms_governance -- the clause register and its compliance check.

Each of the five governing terms in the uploaded contract excerpt is held as
a versioned register entry: Time for Completion, Delay Damages, Defects
Notification Period, Retention and Performance Security. The capability
cites the clause, compares a caller-stated value against the contract, and
submits the term to the governance gate before it can be relied on; the
validation block checks the term's shape through its five-stage pipeline.

READS   the request record and the contract excerpt (app.contract_data).
WRITES  evidence artifacts under STORAGE_PATH/workspace; the ROUTE persists
        the register entry, never this handler.
NEVER   rewrites the contract to match the caller: a divergent value is
        reported as a divergence, with the contract's own value named.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app import contract_data, sources
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "contract_terms_governance"
ENTITY = "contract_terms_governance"
BLOCK_IDS = ["governance_gate", "validation"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

#: Term key -> the unit the contract states for it, and the source term name.
TERM_UNITS = {
    "time_for_completion": ("days", "time_for_completion_days"),
    "delay_damages": ("percent_per_day", "delay_damages_daily_pct"),
    "defects_notification": ("days", "defects_notification_days"),
    "retention": ("percent", "retention_pct"),
    "performance_security": ("percent", "performance_security_pct"),
}


def _contract_value(term_type: str) -> Tuple[Optional[float], str]:
    spec = TERM_UNITS.get(term_type)
    if not spec:
        return None, ""
    unit, source_name = spec
    raw = sources.term(source_name)
    try:
        return (float(raw) if raw is not None else None), unit
    except (TypeError, ValueError):
        return None, unit


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "contract-administrator"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"

    term_type = _support.text_of(record, "term_type").lower()
    if not term_type:
        term_type = next(iter(TERM_UNITS))
    if term_type not in TERM_UNITS:
        return refuse(
            f"{term_type!r} is not a governing term in {contract_data.CONTRACT_DOCUMENT}",
            error_kind="unknown_contract_term",
            input_digest=input_digest,
        )
    clause = sources.clause(term_type)
    if clause is None:
        return refuse(
            f"no clause in {contract_data.CONTRACT_DOCUMENT} defines {term_type}",
            error_kind="missing_clause",
            input_digest=input_digest,
        )

    contract_value, default_unit = _contract_value(term_type)
    stated = record.get("value")
    value = _support.number_of(record, "value", -1.0)
    if value < 0:
        value = contract_value if contract_value is not None else 0.0
        source_of_value = "contract"
    else:
        source_of_value = "caller"
    unit = _support.text_of(record, "unit") or default_unit
    divergence = None
    compliant = None
    if contract_value is not None and source_of_value == "caller":
        compliant = abs(float(value) - float(contract_value)) < 1e-9
        if not compliant:
            divergence = {
                "rule": "precedence.v1.ladder",
                "term": term_type,
                "contract_value": contract_value,
                "caller_value": value,
                "winner": "documents",
                "loser": "caller",
                "winner_layer": 2,
                "loser_layer": 4,
            }

    assessment = {
        "reference": reference,
        "term_type": term_type,
        "clause_ref": str(clause.get("clause") or ""),
        "clause_subject": str(clause.get("subject") or ""),
        "clause_terms": str(clause.get("terms") or ""),
        "value": value,
        "unit": unit,
        "contract_value": contract_value,
        "value_source": source_of_value,
        "compliant": compliant,
        "divergences": [divergence] if divergence else [],
        "source_document": contract_data.CONTRACT_DOCUMENT,
        "citations": [contract_data.CONTRACT_DOCUMENT],
        "authority": "layer 2 documents",
    }

    inputs: Dict[str, Dict[str, Any]] = {
        "governance_gate": {
            "tenant_id": tenant,
            "action_type": f"contract_term:{term_type}",
            "target_id": reference,
            "requester_id": principal,
        },
        "validation": {
            "item": {
                "id": reference,
                "type": term_type,
                "value": value,
                "unit": unit,
            },
            "context": {"project_total_days": contract_data.TIME_FOR_COMPLETION_DAYS},
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"governance_gate": "create_request", "validation": "validate_pipeline"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    workspace = _support.workspace_dir(CAPABILITY_ID)
    artifact = _support.artifact_name("term", assessment)
    _support.write_artifact(workspace, artifact, assessment)
    result = {
        **assessment,
        "term_file": artifact,
        "approval_status": "pending_approval",
        "block_evidence": {
            "governance_requested": isinstance(answers.get("governance_gate"), dict)
            and answers["governance_gate"].get("ok") is not False,
            "validation_run": isinstance(answers.get("validation"), dict)
            and answers["validation"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
