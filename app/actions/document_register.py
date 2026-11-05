"""document_register -- the controlled document register.

Every contract, BOQ, drawing, report and certificate gets one controlled entry:
title, type, revision, checksum and the source document it came from. The
checksum is computed from the document body (or accepted from the caller when
the file itself was hashed on upload), so a later revision can be compared.

READS   the request record, the uploaded contract/BOQ data, and the workspace
        file it writes.
WRITES  the controlled copy under STORAGE_PATH/workspace and this capability's
        result; the ROUTE persists the record, never the handler.
NEVER   registers a document without a checksum, or rewrites an existing
        revision in place.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Dict

from app import contract_data
from app.actions import _support
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "version", "version_diff", "search", "file_hasher", "audit"]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$")


def _semver(revision: str) -> str:
    raw = str(revision or "").strip()
    if _SEMVER.match(raw):
        return raw
    digits = re.findall(r"\d+", raw)
    if len(digits) >= 3:
        return ".".join(digits[:3])
    if len(digits) == 2:
        return f"{digits[0]}.{digits[1]}.0"
    if len(digits) == 1:
        return f"{digits[0]}.0.0"
    return "1.0.0"


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    title = _support.text_of(record, "title") or reference
    document_type = (_support.text_of(record, "document_type") or "report").lower()
    revision = _support.text_of(record, "revision") or "1.0.0"
    source_document = _support.text_of(record, "source_document")
    if not source_document:
        source_document = (
            contract_data.BOQ_DOCUMENT if document_type == "boq" else contract_data.CONTRACT_DOCUMENT
        )

    body = "\n".join(
        [
            f"title: {title}",
            f"reference: {reference}",
            f"document_type: {document_type}",
            f"revision: {revision}",
            f"source_document: {source_document}",
            contract_data.contract_source_text() if document_type == "contract" else "",
        ]
    ).strip()
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    checksum = _support.text_of(record, "checksum") or body_hash

    workspace = _support.workspace_dir(CAPABILITY_ID)
    controlled = workspace / f"register_{reference.replace('/', '_')}_r{_semver(revision)}_{uuid.uuid4().hex[:8]}.txt"
    controlled.write_text(body, encoding="utf-8")
    version_string = _semver(revision)

    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {
            "brief": f"Extract the controlled metadata for {title}:\n{body}",
        },
        "version": {
            "block_id": reference,
            "version": version_string,
            "changelog": [f"Register revision {revision} of {title}"],
            "source_document": source_document,
        },
        "version_diff": {
            "proposals": [],
            "diff": {"new": [], "resolved": [], "regressed": [], "persisting": []},
            "reference": reference,
            "revision": revision,
        },
        "search": {
            "query": f"{title} {revision} {source_document}",
            "text": body,
        },
        "file_hasher": {"file_path": str(controlled)},
        "audit": {
            "action_type": "document_registered",
            "principal_id": _support.text_of(record, "principal_id") or "document-controller",
            "payload": {
                "reference": reference,
                "title": title,
                "revision": revision,
                "checksum": checksum,
                "source_document": source_document,
            },
            "result": {"registered": True, "reference": reference},
            "reference": reference,
        },
    }

    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID, record, BLOCK_IDS, inputs, actions={"version_diff": "score"}
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result = {
        "reference": reference,
        "title": title,
        "document_type": document_type,
        "revision": revision,
        "semver": version_string,
        "checksum": checksum,
        "computed_checksum": body_hash,
        "checksum_matches_supplied": checksum == body_hash or not _support.text_of(record, "checksum"),
        "source_document": source_document,
        "controlled_copy": str(controlled),
        "block_evidence": {
            "parsed": isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False,
            "version_published": isinstance(answers.get("version"), dict)
            and answers["version"].get("ok") is not False,
            "diff_scored": isinstance(answers.get("version_diff"), dict)
            and answers["version_diff"].get("ok") is not False,
            "hashed": isinstance(answers.get("file_hasher"), dict)
            and answers["file_hasher"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 2 documents",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
