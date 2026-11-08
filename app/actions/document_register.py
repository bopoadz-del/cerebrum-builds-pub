"""The controlled document register: hashed, versioned, clause-linked.

Every entry is written to the persistence root, hashed by the file_hasher
block, diffed against the revision it supersedes, and sealed on the audit
chain with the clauses and BOQ items it supports.
"""

from __future__ import annotations

import os
import re

from app import contract_terms as terms
from app.actions._support import (
    as_date, check, block_result, input_digest, iso, ok, principal,
    require_payload, tenant_id,
)
from app.block_inputs import default_block_action, ensure_text_file, storage_root
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "file_hasher", "version_diff", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "app.contract_terms", "STORAGE_PATH"]
SCOPE_WRITES = ["result", "STORAGE_PATH/register"]
SCOPE_NEVER = ["store.save", "network"]


class _Finding:
    """The minimum shape the version_diff contract reads."""

    def __init__(self, element_a, element_b, kind, detail=None):
        self.element_a = str(element_a)
        self.element_b = str(element_b)
        self.kind = str(kind)
        self.detail = detail or {}

    def as_dict(self):
        return {
            "element_a": self.element_a,
            "element_b": self.element_b,
            "kind": self.kind,
            "detail": self.detail,
        }


def _register_file(payload):
    title = str(payload.get("document_title") or payload.get("reference") or "document")
    revision = str(payload.get("document_revision") or "A")
    body = (
        "%s\nRevision %s\nIssued %s\nSupports %s\n"
        % (title, revision, iso(as_date(payload.get("issued_date"))), payload.get("linked_clause") or "")
    )
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)[:60].strip("_") or "document"
    safe_revision = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in revision)[:20] or "A"
    directory = storage_root() / "register"
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / ("%s-%s.txt" % (safe, safe_revision))).resolve()
    root = directory.resolve()
    if not str(path).startswith(str(root) + os.sep):
        raise ValueError("register path escapes the persistence root")
    return ensure_text_file(str(path.relative_to(storage_root())), body), title, revision


def _citation_for(linked_clause):
    """A clause reference is cited with its document, never bare."""
    text = str(linked_clause or "").strip()
    if not text:
        return terms.document_citation(terms.CONTRACT_FILENAME)
    match = re.search(r"([0-9]+(?:\.[0-9]+)+)", text)
    if match and match.group(1) in terms.CLAUSES:
        return terms.clause_citation(match.group(1))
    if text.startswith("document:"):
        return text
    return terms.document_citation(terms.CONTRACT_FILENAME)


def _linked_issues(payload, reference):
    clause = str(payload.get("linked_clause") or "")
    if not clause:
        return []
    return [_Finding(clause, reference, "clash", {"revision": payload.get("document_revision")})]


def handle(payload):
    payload = require_payload(payload)
    reference = str(payload.get("reference") or "document")
    file_path, title, revision = _register_file(payload)

    hash_answer = execute(
        "file_hasher",
        {"file_path": file_path},
        action=BLOCK_DEFAULT_ACTIONS.get("file_hasher"),
    )
    stopped = check("file_hasher", hash_answer)
    if stopped:
        return stopped
    digest = (block_result(hash_answer).get("hashes") or {}).get("sha256") or ""

    linked_clause = str(payload.get("linked_clause") or "")
    linked_clause_valid = bool(linked_clause) and any(
        str(number) in linked_clause for number in terms.CLAUSES
    )
    supersedes = str(payload.get("supersedes") or "")
    previous = []
    if supersedes:
        previous = [_Finding(str(payload.get("linked_clause") or reference), supersedes, "clear")]
    diff_answer = execute(
        "version_diff",
        {"findings_v1": previous, "findings_v2": _linked_issues(payload, reference)},
        action=BLOCK_DEFAULT_ACTIONS.get("version_diff"),
    )
    stopped = check("version_diff", diff_answer)
    if stopped:
        return stopped
    diff = block_result(diff_answer)

    narrative = (
        "Register entry %s: %s revision %s, issued %s, supporting %s."
        % (reference, title, revision, iso(as_date(payload.get("issued_date"))), payload.get("linked_clause") or "the contract")
    )
    document_answer = execute(
        "document_engine",
        {"text": narrative},
        action=BLOCK_DEFAULT_ACTIONS.get("document_engine"),
    )
    stopped = check("document_engine", document_answer)
    if stopped:
        return stopped
    document = block_result(document_answer)

    audit_answer = execute(
        "audit_chain",
        {
            "tenant_id": tenant_id(),
            "action_execution_id": "register-%s" % reference,
            "action_type": "document_registration",
            "principal_id": principal(),
            "project_id": "harbourline-civil-works",
            "payload": {
                "reference": reference,
                "document_title": title,
                "revision": revision,
                "sha256": digest,
                "supersedes": supersedes,
            },
            "result": {"diff": diff},
        },
        action=BLOCK_DEFAULT_ACTIONS.get("audit_chain"),
    )
    stopped = check("audit_chain", audit_answer)
    if stopped:
        return stopped
    audit = block_result(audit_answer)

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "document_title": title,
            "document_revision": revision,
            "sha256": digest,
            "file_hashed": file_path,
            "supersedes": supersedes,
            "linked_clause": linked_clause,
            "linked_clause_valid": linked_clause_valid,
            "version_chain": [
                {"revision": revision, "sha256": digest, "supersedes": supersedes}
            ],
            "diff_new": len(diff.get("new") or []),
            "diff_regressed": len(diff.get("regressed") or []),
            "document_requirements": len(document.get("requirements") or []),
            "audit_chain_hash": (audit.get("record") or {}).get("chain_hash"),
            "input_digest": input_digest(payload),
            "citations": [
                _citation_for(linked_clause),
                terms.document_citation(terms.BOQ_FILENAME)
                if payload.get("document_type") == "boq"
                else terms.clause_citation(terms.DEFECTS_NOTIFICATION),
            ],
            "authority": "documents (layer 2, precedence.v1)",
        }
    )
