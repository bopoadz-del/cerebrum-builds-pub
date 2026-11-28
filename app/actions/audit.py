"""Append-only audit capability with a durable hash chain.

The vendored audit block writes the immutable ledger entry the capability
asks for.  On top of that the capability keeps its own chain over the tenant's
persisted audit records: every record carries its sequence, the digest of its
predecessor and its own canonical digest, so a restart can re-walk the chain
from ``service`` storage rather than an in-process dict.  Verification walks
the persisted rows and names every broken link; it never reports "verified"
for a walk that saw nothing.

SCALE: one event per call.
READS: caller fields; the tenant's persisted audit rows; the block's log.
WRITES: the recorded entry in the response; the route persists the record
        with the chain columns the handler computed.
NEVER: an edit of an existing entry, or a "verified" claim without a walk.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute

CAPABILITY_ID = "audit"
ENTITY = "audit"
BLOCK_IDS = ["audit"]
BLOCK_DEFAULT_ACTIONS = {"audit": "log"}
AUTHORED_BY = "codewhale exec"

#: The block's own default categories (audit block default_config).
RETENTION_DAYS = 2555
CATEGORIES = ("auth", "data_access", "system", "admin")
_CATEGORY_WORDS = {
    "auth": ("login", "auth", "authenticate", "token", "password", "session"),
    "data_access": ("read", "query", "export", "download", "retrieve", "view"),
    "admin": ("config", "grant", "revoke", "approve", "role", "permission"),
}
_SEVERITY = {"open": "notice", "in_progress": "elevated", "closed": "archived"}
_ACTOR_CLASS = {
    "system": "service", "service": "service", "scheduler": "service",
    "automation": "service", "operator": "human_operator", "admin": "human_operator",
    "customer": "counterparty", "contractor": "counterparty",
}


def _canonical(data: Dict[str, Any]) -> Dict[str, Any]:
    """The exact field set the chain digest covers, normalised once."""
    return {
        "reference": str(data.get("reference") or ""),
        "status": str(data.get("status") or ""),
        "notes": str(data.get("notes") or ""),
        "event": str(data.get("event") or ""),
        "resource_type": str(data.get("resource_type") or ""),
        "resource_id": str(data.get("resource_id") or ""),
        "details": str(data.get("details") or ""),
        "actor": str(data.get("actor") or ""),
        "sequence": int(data.get("sequence") or 0),
        "previous_digest": str(data.get("previous_digest") or ""),
    }


def _digest(data: Dict[str, Any]) -> str:
    return domain_rules.canonical_digest(_canonical(data))


def _category(event: str) -> str:
    text = str(event or "").casefold()
    for name, words in _CATEGORY_WORDS.items():
        if any(word in text for word in words):
            return name
    return "unclassified"


def _resource_class(resource_type: str) -> str:
    text = str(resource_type or "").casefold()
    if not text:
        return "unclassified"
    for name in ("booking", "invoice", "contractor", "dispute", "suburb", "config"):
        if name in text:
            return name
    return "other"


def _actor_class(actor: str) -> str:
    text = str(actor or "").strip().casefold()
    return _ACTOR_CLASS.get(text, "human")


def _prior_rows() -> List[Dict[str, Any]]:
    rows = list(domain_rules.tenant_records(ENTITY))
    return sorted(rows, key=lambda row: int(row.get("id") or 0))


def _walk(rows: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Full walk over persisted rows: linkage and per-row digest re-computed."""
    violations: List[Dict[str, Any]] = []
    expected = ""
    for row in rows:
        fields = _canonical(row)
        if fields["previous_digest"] != expected:
            violations.append({"record": row.get("id"), "error": "previous_digest linkage broken"})
        computed = _digest(row)
        stored = str(row.get("chain_digest") or "")
        if computed != stored:
            violations.append({"record": row.get("id"), "error": "chain_digest mismatch"})
        expected = stored
    return (not violations), violations


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "audit")
    event = str(data.get("event") or "record")
    resource_type = str(data.get("resource_type") or "booking")
    resource_id = str(data.get("resource_id") or reference)
    actor = str(data.get("actor") or "system")
    notes = str(data.get("notes") or "")
    details = str(data.get("details") or "")
    status = str(data.get("status") or "open")

    prior = _prior_rows()
    previous_digest = str(prior[-1].get("chain_digest") or "") if prior else ""
    sequence = len(prior) + 1
    chain_fields = {
        "reference": reference,
        "status": status,
        "notes": notes,
        "event": event,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "actor": actor,
        "sequence": sequence,
        "previous_digest": previous_digest,
    }
    chain_digest = _digest(chain_fields)
    verified, violations = _walk(prior)

    entry = execute(
        "audit",
        {
            "event": event,
            "action_name": event,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "details": {
                "reference": reference,
                "notes": notes,
                "details": details,
                "actor": actor,
                "sequence": sequence,
                "previous_digest": previous_digest,
                "chain_digest": chain_digest,
            },
        },
        action=BLOCK_DEFAULT_ACTIONS.get("audit"),
    )
    if block_failed(entry):
        return fail(refusal_text(entry))
    recorded = entry.get("entry") or {}
    stats = execute("audit", {}, action="get_stats")
    if block_failed(stats):
        return fail(refusal_text(stats))

    record = _canonical(chain_fields)
    record.pop("previous_digest", None)
    return ok({
        "reference": reference,
        "status": status,
        "notes": notes,
        "event": event,
        "event_category": _category(event),
        "severity": _SEVERITY.get(status, "unclassified"),
        "resource_type": resource_type,
        "resource_class": _resource_class(resource_type),
        "resource_id": resource_id,
        "details": details,
        "details_present": bool(details),
        "actor": actor,
        "actor_class": _actor_class(actor),
        "block_entry_id": recorded.get("id"),
        "block_process_log_count": stats.get("log_count", 0),
        "block_scope": "process-local (durable record is the audit row)",
        "sequence": sequence,
        "previous_digest": previous_digest,
        "chain_digest": chain_digest,
        "persisted_records": len(prior) + 1,
        "chain_records_walked": len(prior),
        "chain_verified": verified if prior else None,
        "chain_violations": violations,
        "chain_scope": "persisted tenant audit rows",
        "record_bytes": len(json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")),
        "retention_days": RETENTION_DAYS,
        "authority": {"label": "certified", "layer": 1, "basis": "audit block + persisted chain"},
    })
