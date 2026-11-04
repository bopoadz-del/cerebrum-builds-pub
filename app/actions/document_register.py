"""Controlled document register: revision, digest, diff, storage and chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_register"
ENTITY = "document_register"
BLOCK_IDS = ["document_engine", "version", "version_diff", "storage", "audit_chain"]


def _digest(record: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    revision = str(record.get("revision") or "A")
    document_type = str(record.get("document_type") or "drawing")
    supersedes = str(record.get("supersedes") or "")
    approval_state = str(record.get("approval_state") or "pending")
    blocks: Dict[str, Any] = {}

    parsed, error = call("document_engine", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["document_engine"] = {
        "requirements": len(parsed.get("requirements") or []),
        "sections": sorted(k for k, v in parsed.items() if isinstance(v, list) and v),
    }

    published, error = call("version", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["version"] = {
        "version": published.get("version"),
        "published": bool(published.get("published")),
    }

    compared, error = call("version_diff", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    body = compared.get("result") if isinstance(compared.get("result"), dict) else compared
    changes = (body or {}).get("changes") or (body or {}).get("diff") or []
    blocks["version_diff"] = {"changes": len(changes)}

    stored_file, error = call("storage", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    file_id = str(stored_file.get("file_id") or "")
    blocks["storage"] = {"file_id": file_id, "stored": bool(stored_file.get("stored"))}

    chained, error = call("audit_chain", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    chain_record = chained.get("record") if isinstance(chained.get("record"), dict) else {}
    blocks["audit_chain"] = {"evidence_id": chain_record.get("id")}

    digest = _digest(record)
    retired = bool(supersedes) and approval_state != "superseded"
    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "document_type": document_type,
        "revision": revision,
        "supersedes": supersedes,
        "approval_state": approval_state,
        "content_digest": digest,
        "file_id": file_id,
    }
    computed = {
        "content_digest": digest,
        "file_id": file_id,
        "version_published": blocks["version"]["version"],
        "supersedes": supersedes,
        "retires_previous": retired,
        "approval_state": approval_state,
        "evidence_id": chain_record.get("id"),
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("documents"),
    }
