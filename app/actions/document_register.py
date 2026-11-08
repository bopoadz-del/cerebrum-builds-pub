"""document_register -- controlled project documents and revision history.

One register entry pins a document to the source document it belongs to, its
revision, a content checksum and its review status. The register is the
project's system of record for controlled copies: the contract and the bill
of quantities are filed from the uploaded source-of-record documents, and
every further document (ITP, certificate, claim, drawing, report,
correspondence) is filed under its own type and revision.

The register also states who the controlled copy is distributed to. The
distribution groups are derived from the document type -- a contract or a
bill of quantities goes to contracts/commercial and document control, an ITP
to QA/QC and document control -- so the register is complete without a
per-document table of recipients.

READS   the request record, the uploaded contract and BOQ source of record,
        and the tenant's earlier revisions of the same reference.
WRITES  evidence artifacts under STORAGE_PATH/workspace; the ROUTE persists
        the register entry, never this handler.
NEVER   claims a document was reviewed when no reviewer is named, never
        mints a checksum from anything but the document content, and never
        files a revision that rewinds the document's revision chain.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_data, store
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "version_diff", "review", "search"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

#: Which distribution groups receive a controlled copy, by document type.
#: Document control is on every distribution; the discipline group follows
#: the document's own type.
DISTRIBUTION_BY_TYPE: Dict[str, List[str]] = {
    "contract": ["contracts_commercial", "document_control"],
    "boq": ["contracts_commercial", "document_control"],
    "claim": ["contracts_commercial", "document_control"],
    "certificate": ["contracts_commercial", "document_control"],
    "itp": ["qa_qc", "document_control"],
    "drawing": ["engineering", "document_control"],
    "report": ["document_control"],
    "correspondence": ["document_control"],
}

#: Register status -> the review state a document controller reads.
REVIEW_STATE_BY_STATUS: Dict[str, str] = {
    "open": "awaiting_review",
    "in_progress": "in_review",
    "closed": "reviewed",
}


def _revision_history(tenant: str, reference: str) -> List[Dict[str, Any]]:
    """The tenant's earlier revisions of this register entry, oldest first."""
    try:
        rows = store.list_all(CAPABILITY_ID, tenant_id=tenant)
    except Exception:  # noqa: BLE001 - a first run has no table yet
        return []
    history = [
        {
            "id": row.get("id"),
            "revision": row.get("revision"),
            "checksum": row.get("checksum"),
            "document_type": row.get("document_type"),
            "revision_date": row.get("revision_date"),
        }
        for row in rows
        if str(row.get("reference") or "") == reference
    ]
    history.sort(key=lambda row: str(row.get("id") or ""))
    return history


def _source_text(document_type: str, source_document: str) -> str:
    """The citable text of the source document this entry files.

    The contract and the bill of quantities are read from the uploaded
    source-of-record data; every other document type is filed against the
    document it names, without inventing body text it does not have.
    """
    if document_type == "boq":
        return contract_data.boq_source_text()
    if document_type == "contract":
        return contract_data.contract_source_text()
    return f"Controlled copy of {source_document}"


def _next_revision(history: List[Dict[str, Any]]) -> str:
    """The revision letter that follows the last filed one (A, B, ... Z, AA)."""
    def value(revision: str) -> int:
        total = 0
        for char in str(revision or "").upper():
            if "A" <= char <= "Z":
                total = total * 26 + (ord(char) - ord("A") + 1)
        return total

    # A row filed through the POST route carries no revision unless the
    # caller stated one; its position in the chain is its revision.
    numbers = [
        value(row.get("revision") or "") or index + 1
        for index, row in enumerate(history)
    ]
    number = (max(numbers) if numbers else 0) + 1
    letters = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters or "A"


def _distribution(document_type: str) -> List[Dict[str, str]]:
    groups = DISTRIBUTION_BY_TYPE.get(document_type, ["document_control"])
    return [{"group": group, "method": "register", "state": "issued"} for group in groups]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "document-controller"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"

    title = _support.text_of(record, "title") or reference
    document_type = (_support.text_of(record, "document_type") or "contract").lower()
    status = (_support.text_of(record, "status") or "open").lower()
    source_document = _support.text_of(record, "source_document")
    if not source_document:
        source_document = (
            contract_data.BOQ_DOCUMENT
            if document_type == "boq"
            else contract_data.CONTRACT_DOCUMENT
        )
    revision_date = _support.text_of(record, "revision_date") or None

    history = _revision_history(tenant, reference)
    supersedes = history[-1] if history else None
    stated_revision = _support.text_of(record, "revision")
    revision = stated_revision.upper() if stated_revision else _next_revision(history)

    body = _source_text(document_type, source_document)
    content = (
        f"{title}\n"
        f"Controlled document: {source_document}\n"
        f"Document type: {document_type}\n"
        f"Revision: {revision}\n"
        f"Review state: {REVIEW_STATE_BY_STATUS.get(status, 'awaiting_review')}\n"
        f"Source of record excerpt:\n{body}"
    )
    checksum = _support.digest({"title": title, "revision": revision, "content": content})
    refiled = False
    if supersedes and str(supersedes.get("revision") or "").upper() == revision:
        if str(supersedes.get("checksum") or "") == checksum:
            # The same controlled copy filed again is the held copy, not a new
            # revision: the register does not duplicate what it already holds.
            refiled = True
        else:
            return refuse(
                f"revision {revision!r} of {reference!r} is held with different "
                "content; file the change under the next revision",
                error_kind="revision_conflict",
                input_digest=input_digest,
            )
    distribution = _distribution(document_type)

    assessment = {
        "reference": reference,
        "title": title,
        "document_type": document_type,
        "revision": revision,
        "revision_date": revision_date,
        "source_document": source_document,
        "checksum": checksum,
        "revision_count": len(history) + 1,
        "supersedes": supersedes,
        "revision_chain": [
            {"revision": row.get("revision"), "checksum": row.get("checksum")}
            for row in history
        ]
        + ([] if refiled else [{"revision": revision, "checksum": checksum}]),
        "refiled": refiled,
        "review_status": REVIEW_STATE_BY_STATUS.get(status, "awaiting_review"),
        "reviewer": principal if status == "closed" else None,
        "distribution": distribution,
        "citations": [source_document],
        "authority": "layer 2 documents",
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)

    assessment["revision_change"] = {
        "from": (supersedes or {}).get("revision"),
        "to": None if refiled else revision,
        "checksum_changed": bool(
            supersedes is not None
            and str(supersedes.get("checksum") or "") != checksum
        ),
    }

    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {"text": content},
        "version_diff": {"findings_v1": [], "findings_v2": []},
        "review": {"block_id": reference, "limit": 10},
        "search": {"query": f"{title} {reference}", "provider": "mock"},
    }
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions={"review": "get_reviews", "version_diff": "diff"},
    )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    artifact = _support.artifact_name("register", assessment)
    _support.write_artifact(workspace, artifact, assessment)
    result = {
        **assessment,
        "register_file": artifact,
        "block_evidence": {
            "document_parsed": isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False,
            "revision_compared": isinstance(answers.get("version_diff"), dict)
            and answers["version_diff"].get("ok") is not False,
            "review_read": isinstance(answers.get("review"), dict)
            and answers["review"].get("ok") is not False,
            "search_indexed": isinstance(answers.get("search"), dict)
            and answers["search"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
