"""Nudges managers when a work instruction or quality procedure is revised."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.actions._common import block_failure, configured_email, envelope
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_revision_nudges"
ENTITY = "document_revision_nudges"
BLOCK_IDS = ["version_diff", "microsoft_365", "notification", "email", "audit"]
BLOCK_DEFAULT_ACTIONS = {
    "version_diff": None,
    "microsoft_365": None,
    "notification": "send",
    "email": "validate_address",
    "audit": "log",
}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "config", "scope": "runtime"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


@dataclass
class _RevisionClause:
    element_a: str
    element_b: str
    kind: str

    def as_dict(self) -> Dict[str, Any]:
        return {"document": self.element_a, "revision": self.element_b, "kind": self.kind}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    name = str(record.get("document_name") or "plant document")
    revision_from = str(record.get("revision_from") or "")
    revision_to = str(record.get("revision_to") or "")
    changed = bool(revision_from and revision_to and revision_from != revision_to)

    move = bool(revision_from and revision_to and revision_from != revision_to)
    old_findings = [_RevisionClause(name, revision_from, "clear")] if move else []
    new_findings = [_RevisionClause(name, revision_to, "clash")] if move else []
    diff = execute(
        "version_diff",
        {"findings_v1": old_findings, "findings_v2": new_findings},
        action=BLOCK_DEFAULT_ACTIONS.get("version_diff"),
    )
    refused = block_failure("version_diff", diff)
    if refused:
        return refused

    m365 = execute(
        "microsoft_365",
        {"action": "status"},
        action=BLOCK_DEFAULT_ACTIONS.get("microsoft_365"),
    )
    refused = block_failure("microsoft_365", m365)
    if refused:
        return refused

    notice = execute(
        "notification",
        {
            "channel": "mcp",
            "block": "audit",
            "payload": {"reference": name, "revision_to": revision_to},
            "message": f"{name} revised to {revision_to or 'a new revision'}",
        },
        action=BLOCK_DEFAULT_ACTIONS.get("notification"),
    )
    refused = block_failure("notification", notice)
    if refused:
        return refused

    mail = execute(
        "email",
        {"email": configured_email(record)},
        action=BLOCK_DEFAULT_ACTIONS.get("email"),
    )
    refused = block_failure("email", mail)
    if refused:
        return refused

    trail = execute(
        "audit",
        {"event": "document_revision_nudge", "actor": "platform", "details": {"document_name": name}},
        action=BLOCK_DEFAULT_ACTIONS.get("audit"),
    )
    refused = block_failure("audit", trail)
    if refused:
        return refused

    return envelope(
        {
            "document_name": name,
            "document_type": str(record.get("document_type") or "work_instruction"),
            "revision_from": revision_from,
            "revision_to": revision_to,
            "changed": changed,
            "diff": {
                "new": len(diff.get("new") or []),
                "resolved": len(diff.get("resolved") or []),
                "regressed": len(diff.get("regressed") or []),
                "persisting": len(diff.get("persisting") or []),
            },
            "m365_connections": int(m365.get("connections") or 0),
            "notification_sent": bool(notice.get("sent")),
            "email_valid": bool(mail.get("valid")),
            "email_sent": False,
            "email_delivery": "outlook adapter not configured; address validated only",
            "audit_entry": (trail.get("entry") or {}).get("id"),
        },
        record,
    )
