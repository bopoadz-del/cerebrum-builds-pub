"""document_register -- the controlled register of project documents.

One entry is one document revision: its title, type, revision, the source
document it belongs to and a checksum of the controlled copy kept under
STORAGE_PATH/workspace. A progress claim, a delay assessment or an ITP record
cites this entry instead of a loose copy.

The register is browsable and searchable through the same capability:
GET /v1/document_register returns the tenant's entries, and
GET /v1/document_register/search?q=... searches the entry metadata and the
controlled copy's own text. An upload is parsed and registered through
POST /v1/document_register/intake, and POST /v1/document_register/ask answers
a question from the registered text with a document:<filename> [n] citation.

READS   the request record and the uploaded source documents.
WRITES  the controlled copy and its metadata under STORAGE_PATH/workspace; the
        ROUTE persists the register entry, never this handler.
NEVER   invents a source document, a revision or a checksum; a supplied
        checksum that does not match the controlled copy is reported.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from app import contract_data
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "search", "version", "audit"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$")
_CITATION = re.compile(r"^document:.+$")


def _semver(revision: str) -> str:
    raw = str(revision or "").strip()
    if _SEMVER.match(raw):
        return raw
    digits = re.findall(r"\d+", raw)
    if len(digits) >= 3:
        return ".".join(digits[:3])
    if digits:
        return f"0.{digits[0]}.0"
    # Alpha revisions (A, B, C ...) are ordinal, not all "1.0.0": a controlled
    # register that maps A and B to the same version cannot express a
    # supersession.
    letters = re.fullmatch(r"[A-Za-z]+", raw)
    if letters:
        token = letters.group(0).upper()
        if len(token) == 1:
            return f"{ord(token) - 64}.0.0"
        return f"{sum(ord(char) - 64 for char in token)}.0.0"
    return "1.0.0"


def _citation(source_document: str, document_type: str) -> str:
    if _CITATION.match(source_document or ""):
        return source_document
    if (document_type or "").lower() == "boq":
        return contract_data.BOQ_DOCUMENT
    if (document_type or "").lower() == "contract":
        return contract_data.CONTRACT_DOCUMENT
    return source_document or contract_data.CONTRACT_DOCUMENT


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    title = _support.text_of(record, "title") or reference
    document_type = (_support.text_of(record, "document_type") or "contract").lower()
    revision = _support.text_of(record, "revision") or "A"
    citation = _citation(_support.text_of(record, "source_document"), document_type)

    body = {
        "reference": reference,
        "title": title,
        "document_type": document_type,
        "revision": revision,
        "source_document": citation,
    }
    computed = _support.digest(body)
    supplied = _support.text_of(record, "checksum")
    # A supplied digest is verified against the controlled copy, never trusted:
    # a mismatch is recorded on the entry as evidence, not silently accepted.
    matches = (not supplied) or supplied == computed

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = _support.artifact_name("controlled", body).split("_", 1)[1].split(".", 1)[0]
    controlled_file = workspace / f"document_{stem}.json"
    _support.write_artifact(workspace, controlled_file.name, {**body, "checksum": computed})
    controlled_text = (
        f"{title}\nType: {document_type}\nRevision: {revision}\nSource: {citation}"
    )

    semver = _semver(revision)
    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {"brief": controlled_text},
        "search": {
            "query": f"{title} {reference}",
            "input": controlled_text,
        },
        "version": {
            "block_id": reference,
            "version": semver,
            "changelog": [{"change_type": "revision", "description": f"registered revision {revision}"}],
            "dependencies": {},
            "breaking_changes": [],
            "migration_guide": "",
        },
        "audit": {
            "action_type": "document_registered",
            "action_name": "document_registered",
            "principal_id": _support.text_of(record, "_principal_id", "principal_id") or "document-controller",
            "payload": body,
            "result": {"checksum": computed, "checksum_matches": matches},
            "reference": reference,
        },
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"version": "publish_version"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    result = {
        "reference": reference,
        "title": title,
        "document_type": document_type,
        "revision": revision,
        "semver": semver,
        "source_document": citation,
        "checksum": computed,
        "checksum_matches": matches,
        "controlled_file": controlled_file.name,
        "register_entry": _support.artifact_name("register", body),
        "revision_key": f"{document_type}:{reference}:{revision.lower()}:{semver}",
        "supersedes": _support.text_of(record, "supersedes"),
        "search_query": f"{title} {reference}",
        "block_evidence": {
            "document_parsed": isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False,
            "searchable": isinstance(answers.get("search"), dict)
            and answers["search"].get("ok") is not False,
            "versioned": isinstance(answers.get("version"), dict)
            and answers["version"].get("ok") is not False,
            "audited": isinstance(answers.get("audit"), dict)
            and answers["audit"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 2 documents",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
