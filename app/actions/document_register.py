"""document_register -- project documents, revisions and provenance.

Maintains the register of incoming and outgoing correspondence, drawings,
submittals, transmittals and contract instructions, each with revision
control, distribution and a tamper-evident audit trail. The uploaded
contract and BOQ are the two documents the register treats as the source of
record.

Scope READS: caller payload, app/sources.py, the vendored blocks.
Scope WRITES: caller output only.
Scope NEVER: no network, no invented document or checksum.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict

from app import sources
from app.actions._artifacts import Workspace
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    record_of,
    refusal,
    success,
    tenant_scope,
    text_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_register"
ENTITY = CAPABILITY_ID

BLOCK_IDS = ["document_engine", "version", "file_hasher", "audit_chain", "search", "notification"]

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "document_engine": None,
    "version": "publish_version",
    "file_hasher": "hash",
    "audit_chain": "record_evidence",
    "search": None,
    "notification": "send",
}

AUTHORITY = authority(CAPABILITY_ID, 2, "documents")

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _revision_semver(revision: str) -> str:
    """A semver for the block. A register revision labels a document; the
    block's own contract requires semver, so a revision that already is one
    is used unchanged and the first issue is 1.0.0."""
    text = str(revision or "").strip().lstrip("vV")
    return text if _SEMVER.match(text) else "1.0.0"


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    document_number = text_of(record.get("document_number")) or text_of(record.get("reference")) or "DOC-draft"
    title = text_of(record.get("title")) or "project document"
    revision = text_of(record.get("revision")) or "1.0.0"
    document_type = text_of(record.get("document_type")) or "submittal"
    issued_by = text_of(record.get("issued_by")) or "document-controller"
    source_document = text_of(record.get("source_document"))
    known_source = source_document in (sources.CONTRACT_DOCUMENT, sources.BOQ_DOCUMENT)
    body = "\n".join(
        [
            "Document register entry",
            "Document: %s" % document_number,
            "Title: %s" % title,
            "Type: %s" % document_type,
            "Revision: %s" % revision,
            "Issued by: %s" % issued_by,
            "Source of record: %s" % (source_document or "not declared"),
        ]
    )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    workspace = Workspace("harbourline-register-")
    try:
        file_path = workspace.write_text("%s-%s.txt" % (document_number.replace("/", "-"), revision), body)
        inputs: Dict[str, Dict[str, Any]] = {
            "document_engine": {"text": body},
            "version": {
                "block_id": document_number,
                "version": _revision_semver(revision),
                "changelog": ["registered revision %s" % revision],
            },
            "file_hasher": {"file_path": file_path, "algorithms": ["sha256"]},
            "audit_chain": {
                "action_execution_id": "register-" + digest[:16],
                "action_type": "document_registered",
                "principal_id": issued_by,
                "payload": {"document": document_number, "revision": revision},
                "result": {"checksum": digest},
            },
            "search": {
                "query": "%s %s" % (document_number, title),
                "_params": {"provider": "mock"},
            },
            "notification": {
                "channel": "mcp",
                "block": "event_bus",
                "payload": {
                    "topic": "document_register.entry",
                    "payload": {
                        "document_number": document_number,
                        "revision": revision,
                        "checksum": digest,
                    },
                    "message": "Document %s revision %s registered" % (document_number, revision),
                    "channel": "mcp",
                    "tool": "event_bus",
                },
                "message": "Document %s revision %s registered" % (document_number, revision),
                "recipient": tenant_scope(),
            },
        }
        answers, refusals = call_blocks(
            BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
        )
    finally:
        workspace.close()

    if refusals:
        return refusal(
            CAPABILITY_ID, AUTHORITY, refusals, answers,
            input_digest=record.get("_input_digest"),
        )

    hasher = answers.get("file_hasher") or {}
    checksum = (hasher.get("hashes") or {}).get("sha256") if isinstance(hasher, dict) else None
    return success(
        CAPABILITY_ID,
        AUTHORITY,
        answers,
        input_digest=record.get("_input_digest"),
        result={
            "document_number": document_number,
            "title": title,
            "document_type": document_type,
            "revision": revision,
            "issued_by": issued_by,
            "issued_date": text_of(record.get("issued_date")),
            "checksum": checksum or digest,
            "source_document": source_document or None,
            "source_is_record": known_source,
            "distribution": text_of(record.get("distribution")),
            "version_block_semver": _revision_semver(revision),
            "citations": sources.citations(),
        },
    )
