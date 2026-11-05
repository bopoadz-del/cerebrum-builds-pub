"""document_register -- controlled register with revision and search.

READS  caller payload, the contract/BOQ document identities and their content
       summaries, and the registered revision.
WRITES the capability response envelope only.
NEVER  seeds a document corpus, invents a checksum, or registers a document
       whose textual extraction refused.
"""

from __future__ import annotations

import hashlib

from app import formulas
from app.authority import authority_label
from app.block_inputs import (
    block_action,
    boq_citation,
    contract_citation,
    document_search_query,
    document_text,
    semver,
)
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "search", "version"]


def _refuse(block_id, answer):
    message = answer.get("error") if isinstance(answer, dict) else answer
    return {
        "ok": False,
        "error": str(block_id) + ": " + str(message or "block refused"),
        "block": block_id,
        "record": None,
        "id": None,
    }


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def handle(payload: dict) -> dict:
    data = dict(payload or {})
    reference = str(data.get("reference") or "DOC-REGISTER")
    text = document_text(data)
    query = document_search_query(data)
    revision = semver(data.get("revision"))
    source = str(data.get("source_document") or contract_citation())
    checksum = str(data.get("checksum") or _checksum(text))

    try:
        extraction = execute(
            "document_engine",
            {"text": text},
            action=block_action("document_engine"),
        )
    except Exception as exc:  # noqa: BLE001
        return _refuse("document_engine", {"error": f"{type(exc).__name__}: {exc}"})
    if not isinstance(extraction, dict) or str(extraction.get("status") or "").lower() == "error":
        return _refuse("document_engine", extraction)

    try:
        search = execute(
            "search",
            {"query": query},
            action=block_action("search"),
            params={"provider": "mock", "num_results": 5},
        )
    except Exception as exc:  # noqa: BLE001
        return _refuse("search", {"error": f"{type(exc).__name__}: {exc}"})
    if not isinstance(search, dict) or str(search.get("status") or "").lower() in {"error", "failed"}:
        return _refuse("search", search)

    try:
        version = execute(
            "version",
            {
                "block_id": "document-register:" + reference[:48],
                "version": revision,
            },
            action="validate_version",
        )
    except Exception as exc:  # noqa: BLE001
        return _refuse("version", {"error": f"{type(exc).__name__}: {exc}"})
    if not isinstance(version, dict) or version.get("valid") is False:
        return _refuse("version", version.get("error") if isinstance(version, dict) else version)

    record = {
        "id": None,
        "reference": reference,
        "status": str(data.get("status") or "open"),
        "title": str(data.get("title") or reference),
        "document_type": str(data.get("document_type") or "specification"),
        "revision": revision,
        "issued_date": data.get("issued_date"),
        "source_document": source,
        "checksum": checksum,
        "supersedes": str(data.get("supersedes") or ""),
        "description": text,
        "search_query": query,
    }
    return {
        "ok": True,
        "record": record,
        "id": None,
        "search_hits": int(search.get("total") or len(search.get("results") or [])),
        "version_valid": bool(version.get("valid")),
        "registered_sources": {
            "contract": contract_citation(),
            "boq": boq_citation(),
        },
        "authority": authority_label(
            "contract",
            detail="register identity and revision from " + source,
        ),
    }
