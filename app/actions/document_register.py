"""document_register — the controlled register of contract, BOQ, drawings and
correspondence.

The register's source of record is the uploaded contract excerpt and BOQ
(document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf,
document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx). Every entry
carries the hash of the text it registers, its provenance, and the revision
the version block accepts.

READS:  the capability payload, both uploaded documents, block answers.
WRITES: the register entry returned to the route (the route persists it).
NEVER:  invents a source document, or registers a revision the version block
        refuses.
"""

from __future__ import annotations

from typing import Any, Dict

from app import contract, dispatch, models
from app.actions._common import (
    BlockRefused,
    as_date,
    call,
    digest,
    envelope,
    refusal,
    scratch_path,
)

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "file_hasher", "ingestion_provenance", "version"]
BLOCK_DEFAULT_ACTIONS = {block: dispatch.default_action(block) for block in BLOCK_IDS}

_SOURCES = {
    contract.contract_document_id(): "contract",
    contract.boq_document_id(): "boq",
}


def _source_text(source: str) -> str:
    if source == contract.contract_document_id():
        return "\n".join(
            f"Clause {row.get('ref')} {row.get('heading', '')}: {row.get('text', '')}"
            for row in contract.clauses()
        )
    if source == contract.boq_document_id():
        header = "Item,Section,Description,Unit,Qty,Rate"
        rows = [
            ",".join(
                [
                    str(item.get("item_code", "")),
                    str(item.get("section", "")),
                    str(item.get("description", "")).replace(",", " "),
                    str(item.get("unit", "")),
                    str(item.get("quantity", "")),
                    str(item.get("rate", "")),
                ]
            )
            for item in contract.boq_items()
        ]
        return "\n".join([header, *rows])
    return ""


def handle(payload: Dict[str, Any], tenant_id: str = "local") -> Dict[str, Any]:
    data = dict(payload or {})
    model = models.DocumentRegisterEntry.from_dict(data)
    record = model.to_dict()

    source = str(data.get("source_document") or "").strip()
    if source and source not in _SOURCES:
        return refusal(
            "source_document must be one of the uploaded documents: "
            + ", ".join(sorted(_SOURCES)),
            field="source_document",
        )
    if not source:
        source = contract.contract_document_id()

    text = _source_text(source)
    if not text:
        return refusal(f"no text is registered for {source}", field="source_document")

    revision = str(data.get("revision") or "1.0.0")
    number = str(data.get("document_number") or data.get("reference") or "document")
    path = scratch_path(f"register-{number}", ".txt")
    path.write_text(text, encoding="utf-8")

    try:
        parsed = call(
            "document_engine",
            {"text": text, "document_id": source, "document_type": _SOURCES.get(source)},
            action=None,
        )
        hashed = call("file_hasher", {"file_path": str(path)}, action="hash")
        provenance = call(
            "ingestion_provenance",
            {
                "source": {
                    "name": source,
                    "kind": _SOURCES.get(source, "document"),
                    "path": str(path),
                }
            },
            action="build",
        )
        version = call(
            "version",
            {"version": revision, "block_id": number},
            action="validate_version",
        )
    except BlockRefused as exc:
        try:
            path.unlink()
        except OSError:
            pass
        return refusal(exc.message)

    try:
        path.unlink()
    except OSError:
        pass

    checksum = str(
        hashed.get("hash")
        or hashed.get("sha256")
        or hashed.get("digest")
        or digest(text)
    )
    result = {
        "entry": {
            "document_number": number,
            "document_type": data.get("document_type") or _SOURCES.get(source),
            "revision": revision,
            "source_document": source,
            "checksum": checksum,
            "supersedes": data.get("supersedes"),
            "issued_date": (as_date(data.get("issued_date")) or "").isoformat()
            if as_date(data.get("issued_date"))
            else None,
            "title": data.get("title") or _SOURCES.get(source, "document"),
        },
        "document": {
            "documents_parsed": parsed.get("documents_parsed"),
            "requirements": len(parsed.get("requirements") or []),
            "raw_text_chars": len(str(parsed.get("raw_text") or "")),
        },
        "hash": {
            "algorithm": hashed.get("algorithm") or hashed.get("algo") or "sha256",
            "checksum": checksum,
            "block": "file_hasher",
        },
        "provenance": {
            "block": "ingestion_provenance",
            "generated_at": (provenance.get("provenance") or {}).get("generated_at"),
            "inputs_hash": (provenance.get("provenance") or {}).get("inputs_hash"),
        },
        "version": {
            "valid": version.get("valid"),
            "major": version.get("major"),
            "minor": version.get("minor"),
            "micro": version.get("micro"),
        },
        "authority": {
            "layer": "documents",
            "label": "L2 documents",
            "source": source,
        },
    }
    record["checksum"] = checksum
    record["source_document"] = source
    record["revision"] = revision
    if not record.get("document_type"):
        record["document_type"] = _SOURCES.get(source)
    return envelope(record, result)
