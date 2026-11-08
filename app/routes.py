"""The platform's HTTP surface: one tenant-scoped route family per capability.

Shape of a capability route, and the reason for each part:
  * authenticate at the edge (401 without a token);
  * validate the payload against the capability's own model -- a missing
    required field or an out-of-vocabulary value is 422 with the field named;
  * run the handler, and refuse with its answer when it fails closed;
  * persist the REQUEST through the tenant-scoped store (never the handler,
    which has no tenant), then answer {ok, id, record, result, authority}.
"""

from __future__ import annotations

import importlib
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app import (
    authority,
    config,
    dispatch,
    document_intake,
    jobs,
    placeholders,
    security,
    sources,
    store,
)
from app import SCREENS as UI_SCREENS
from app.models import MODELS
from app.validation import validate_payload

#: Kernel metadata. Reads that expose the tenant's records authenticate in
#: their own body; the public roster and the UI manifest do not, so a console
#: can discover what the platform serves before it has a deploy token.
KERNEL = APIRouter(prefix="/v1", tags=["kernel"])
#: The register's intake, search and question surfaces. Registered BEFORE the
#: capability family so /v1/document_register/search is not read as a record id.
INGEST = APIRouter(prefix="/v1", tags=["document-register"])
#: The capability family. Authentication is enforced inside each route rather
#: than as a router dependency: a malformed body is refused by the schema (422)
#: before a tenant is needed, and every valid request still authenticates.
ROUTER = APIRouter(prefix="/v1", tags=["capabilities"])

#: capability -> the entity its route saves to. The entity IS the capability id
#: (the stem of its handler module), declared here so a reader never guesses.
ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in MODELS.items()}

#: capability -> the precedence layer its answer is labelled with.
ROUTE_AUTHORITY: Dict[str, str] = {
    "progress_claim_management": "improvised, no Store coverage",
    "delay_damages_tracking": "improvised, no Store coverage",
    "qa_itp_records": authority.label(3),
    "document_register": authority.label(2),
    "contract_terms_governance": authority.label(2),
    "commercial_dashboard": authority.label(3),
}


def _field_specs(capability_id: str) -> List[Dict[str, Any]]:
    model = MODELS.get(capability_id)
    if model is None:
        return []
    constraints = getattr(model, "CONSTRAINTS", {}) or {}
    rows: List[Dict[str, Any]] = []
    for name in model.FIELDS:
        spec = dict(constraints.get(name) or {})
        row: Dict[str, Any] = {
            "name": name,
            "type": spec.get("type", "str"),
            "required": bool(spec.get("required")),
        }
        for key in ("allowed_values", "min", "max", "format", "max_length"):
            if key in spec:
                row[key] = spec[key]
        rows.append(row)
    return rows


def _module(capability_id: str):
    return importlib.import_module("app.actions." + capability_id.replace("-", "_"))


def _rejection(violation: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=security.rejected(violation),
        headers=security.rejection_headers(violation),
    )


_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\[^\s'\"]*|/(?:[^\s'\":]+/)+[^\s'\":]*)")


def _public_error(text: str) -> str:
    """The refusal text as a caller may read it: filesystem paths removed.

    A block's exception text can name a vendored module by absolute path;
    the caller needs the refusal, not the deployment's layout. The full text
    stays in the request log, keyed by request id.
    """
    cleaned = _ABSOLUTE_PATH.sub("<path>", str(text or "")).strip()
    return cleaned[:500] or "the capability refused"


def _refusal(result: Dict[str, Any]) -> JSONResponse:
    kind = str(result.get("error_kind") or "refused")
    body = {
        "ok": False,
        "error": _public_error(result.get("error") or "the capability refused"),
        "error_kind": kind,
    }
    if result.get("blocks"):
        body["blocks"] = result["blocks"]
    if result.get("blocks_unavailable"):
        body["blocks_unavailable"] = result["blocks_unavailable"]
    return JSONResponse(status_code=status.HTTP_200_OK, content=body)


def _create(capability_id: str, payload: Dict[str, Any], principal) -> JSONResponse:
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    placeholder = placeholders.refusal(capability_id)
    if placeholder is not None:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=placeholder)

    values, violations = validate_payload(model, payload)
    if violations:
        return _rejection(violations[0])

    module = _module(capability_id)
    if not hasattr(module, "handle"):
        raise HTTPException(status_code=501, detail="capability has no handler")

    handler_payload = dict(values)
    handler_payload["reference"] = values.get("reference") or ""
    handler_payload["_tenant_id"] = principal.tenant_id
    # The authenticated principal, never a caller-supplied name, names the
    # person an audit or evidence step records.
    handler_payload["_principal_id"] = principal.tenant_id
    result = module.handle(handler_payload)
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="capability returned an invalid answer")
    if result.get("ok") is not True:
        return _refusal(result)

    stored = store.save(model.ENTITY, values, tenant_id=principal.tenant_id)
    body = {
        "ok": True,
        "capability_id": capability_id,
        "id": stored.get("id"),
        "stored": stored,
        "record": stored,
        "result": result.get("result"),
        "authority": result.get("authority")
        or ROUTE_AUTHORITY.get(capability_id)
        or authority.label(3),
        "tenant_id": principal.tenant_id,
    }
    inner = result.get("result") if isinstance(result.get("result"), dict) else {}
    if inner.get("blocks_unavailable"):
        body["blocks_unavailable"] = inner["blocks_unavailable"]
    return JSONResponse(status_code=status.HTTP_200_OK, content=body)


# --- controlled register: intake, search and cited answers ---------------

#: A controlled copy is bounded: a project document is not larger than this,
#: and an unbounded read lets a caller fill the storage root.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

INTAKE_GUIDE = {
    "ok": True,
    "capability_id": "document_register",
    "intake": "POST a multipart file (PDF, XLSX, CSV or text) to this path",
    "parse": "POST a multipart file to /v1/document_register/parse for text only",
    "search": "GET /v1/document_register/search?q=<terms>",
    "ask": "POST {\"question\": \"<question>\"} to /v1/document_register/ask",
    "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
}


@INGEST.get("/document_register/intake")
def intake_guide():
    return dict(INTAKE_GUIDE)


@INGEST.get("/document_register/ask")
def ask_guide():
    return dict(INTAKE_GUIDE)


def _upload_bytes(upload: UploadFile) -> tuple:
    """The uploaded bytes, refused when empty or over the declared bound."""
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    filename = upload.filename or "upload"
    if len(data) > MAX_UPLOAD_BYTES:
        return None, filename, {
            "field": "file",
            "reason": "too_large",
            "message": f"the uploaded file exceeds {MAX_UPLOAD_BYTES} bytes",
        }
    if not data:
        return None, filename, {
            "field": "file",
            "reason": "empty_file",
            "message": "the uploaded file is empty",
        }
    return data, filename, None


def _next_revision(latest: Optional[Dict[str, Any]]) -> str:
    """The revision letter after the copy the tenant already holds."""
    if not latest:
        return "A"
    previous = str(latest.get("revision") or "A")
    letter = previous[:1].upper()
    cycle = previous[1:] or "1"
    if not ("A" <= letter <= "Z"):
        return "A"
    if letter == "Z":
        try:
            return "A" + str(int(cycle) + 1)
        except ValueError:
            return "A2"
    return chr(ord(letter) + 1) + (cycle if cycle != "1" else "")


def _parse_upload(upload: UploadFile) -> JSONResponse:
    data, filename, violation = _upload_bytes(upload)
    if violation is not None:
        return _rejection(violation)
    parsed = document_intake.parse_document(filename, data)
    if not parsed["text"].strip():
        return _rejection(
            {
                "field": "file",
                "reason": "no_extractable_text",
                "message": "the uploaded file carries no extractable text",
            }
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "ok": True,
            "capability_id": "document_register",
            "parsed": True,
            "filename": parsed["filename"],
            "document_type": parsed["document_type"],
            "checksum": parsed["checksum"],
            "characters": parsed["characters"],
            "lines": parsed["lines"],
            "excerpt": parsed["text"][:280],
            "text": parsed["text"],
            "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
        },
    )


@INGEST.get("/document_register/parse")
def parse_uploaded_document_guide(request: Request):
    """The parse endpoint is POST-only; say so instead of colliding with the
    record reader, which would answer 404 for a POST-only sub-resource."""
    security.optional_principal(request)
    return JSONResponse(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        content={
            "ok": False,
            "error": "POST a multipart file to /v1/document_register/parse for text only",
        },
        headers={"Allow": "POST"},
    )


@INGEST.post("/document_register/parse")
def parse_uploaded_document(request: Request, file: UploadFile = File(...)):
    """Parse an attached copy and return its text; nothing is stored.

    This is the console's read-only intake preview. Filing the copy in the
    controlled register is the tenant-scoped POST below.
    """
    security.principal_from_request(request)
    return _parse_upload(file)


@INGEST.post("/document_register/intake")
def intake_document(request: Request, file: UploadFile = File(...)):
    """Parse an uploaded document and file it in the tenant's register.

    The parsed text is kept under the one storage root and keyed by the
    register entry's checksum, so a later question is answered from the copy
    this tenant actually attached, never from a guess.
    """
    principal = security.principal_from_request(request)
    data, filename, violation = _upload_bytes(file)
    if violation is not None:
        return _rejection(violation)
    parsed = document_intake.parse_document(filename, data)
    if not parsed["text"].strip():
        return _rejection(
            {
                "field": "file",
                "reason": "no_extractable_text",
                "message": "the uploaded file carries no extractable text",
            }
        )
    model = MODELS.get("document_register")
    if model is None:
        raise security.not_found("capability")
    # A register entry is one revision of one controlled document: the
    # reference is stable per file name, the revision advances on a new
    # checksum, and re-filing identical bytes returns the copy already held.
    reference = "intake:" + parsed["title"][:80]
    try:
        held = store.list_all(model.ENTITY, tenant_id=principal.tenant_id)
    except KeyError:
        held = []
    history = [
        row
        for row in held
        if str(row.get("reference") or "") == reference
    ]
    latest = history[-1] if history else None
    if latest is not None and str(latest.get("checksum") or "") == parsed["checksum"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": True,
                "capability_id": "document_register",
                "id": latest.get("id"),
                "record": latest,
                "parsed": True,
                "unchanged": True,
                "intake": {
                    "filename": filename,
                    "characters": parsed["characters"],
                    "lines": parsed["lines"],
                    "document_type": latest.get("document_type"),
                    "text_file": document_intake.keep_text(
                        principal.tenant_id, parsed["checksum"], parsed["text"]
                    ),
                    "excerpt": parsed["text"][:280],
                },
                "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
            },
        )
    values = {
        "reference": reference,
        "title": parsed["title"],
        "document_type": parsed["document_type"],
        "revision": _next_revision(latest),
        "source_document": f"document:{filename}",
        "checksum": parsed["checksum"],
        "status": "open",
    }
    validated, violations = validate_payload(model, values)
    if violations:
        return _rejection(violations[0])
    stored = store.save(model.ENTITY, validated, tenant_id=principal.tenant_id)
    text_file = document_intake.keep_text(
        principal.tenant_id, parsed["checksum"], parsed["text"]
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "ok": True,
            "capability_id": "document_register",
            "id": stored.get("id"),
            "record": stored,
            "parsed": True,
            "intake": {
                "filename": filename,
                "characters": parsed["characters"],
                "lines": parsed["lines"],
                "document_type": parsed["document_type"],
                "text_file": text_file,
                "excerpt": parsed["text"][:280],
            },
            "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
        },
    )


@INGEST.get("/document_register/search")
def search_document_register(
    request: Request,
    q: str = "",
    document_type: str = "",
):
    principal = security.principal_from_request(request)
    items = document_intake.search_entries(
        principal.tenant_id, query=q, document_type=document_type
    )
    return {
        "ok": True,
        "capability_id": "document_register",
        "query": q,
        "document_type": document_type,
        "items": items,
        "total": len(items),
        "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
    }


@INGEST.post("/document_register/ask")
def ask_document_register(request: Request, payload: Optional[Dict[str, Any]] = None):
    """Answer a question, citing the document each passage came from.

    The tenant's registered copies are searched first; a copy the caller
    attached in the same request is the fallback, labelled as such.
    """
    principal = security.principal_from_request(request)
    body = payload or {}
    question = str(body.get("question") or "").strip()
    if not question:
        return _rejection(
            {
                "field": "question",
                "reason": "missing_required",
                "message": "a question is required",
            }
        )
    supplied = body.get("documents")
    found = document_intake.answer(principal.tenant_id, question)
    if found.get("ok") is not True and isinstance(supplied, list) and supplied:
        found = document_intake.answer_from_documents(question, supplied)
    if found.get("ok") is not True:
        found = document_intake.source_of_record_answer(question)
    if found.get("ok") is not True:
        return JSONResponse(status_code=status.HTTP_200_OK, content=found)
    return {
        "ok": True,
        "capability_id": "document_register",
        "question": question,
        "answer": found["answer"],
        "citations": found["citations"],
        "authority": found["authority"],
    }


@ROUTER.post("/{capability_id}")
def create_capability_record(
    capability_id: str, request: Request, payload: Optional[Dict[str, Any]] = None
):
    principal = security.principal_from_request(request)
    return _create(capability_id, dict(payload or {}), principal)


@ROUTER.get("/{capability_id}")
def list_capability_records(capability_id: str, request: Request):
    """The capability's catalogue entry, and its tenant's records when signed in.

    A caller with no credential gets the public entry (an empty record list),
    so a console or a monitor can discover the route without holding a token.
    Tenant records are only ever read for the authenticated principal.
    """
    principal = security.optional_principal(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    items = (
        store.list_all(model.ENTITY, tenant_id=principal.tenant_id)
        if principal is not None
        else []
    )
    body = {
        "ok": True,
        "capability_id": capability_id,
        "entity": model.ENTITY,
        "items": items,
        "total": len(items),
        "authority": ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
    }
    if principal is None:
        body["authenticated"] = False
        body["note"] = "tenant records require a bearer token; this is the public entry"
    return body


@ROUTER.get("/{capability_id}/{item_id}")
def read_capability_record(capability_id: str, item_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    record = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if record is None:
        raise security.not_found("record")
    return {
        "ok": True,
        "capability_id": capability_id,
        "record": record,
        "authority": ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
    }


@ROUTER.put("/{capability_id}/{item_id}")
def update_capability_record(
    capability_id: str, item_id: str, payload: Dict[str, Any], request: Request
):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    existing = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if existing is None:
        raise security.not_found("record")
    merged = {key: existing.get(key) for key in model.FIELDS if existing.get(key) is not None}
    merged.update({key: value for key, value in (payload or {}).items() if key in model.FIELDS})
    values, violations = validate_payload(model, merged)
    if violations:
        return _rejection(violations[0])
    updated = store.update(model.ENTITY, item_id, values, tenant_id=principal.tenant_id)
    if updated is None:
        raise security.not_found("record")
    return {
        "ok": True,
        "capability_id": capability_id,
        "id": updated.get("id"),
        "record": updated,
        "authority": ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
    }


@ROUTER.delete("/{capability_id}/{item_id}")
def delete_capability_record(capability_id: str, item_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    record = store.get(model.ENTITY, item_id, tenant_id=principal.tenant_id)
    if record is None:
        raise security.not_found("record")
    if not store.delete(model.ENTITY, item_id, tenant_id=principal.tenant_id):
        raise security.not_found("record")
    return {
        "ok": True,
        "capability_id": capability_id,
        "deleted": True,
        "id": record.get("id"),
        "authority": ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
    }


@KERNEL.get("/jobs")
def kernel_jobs(request: Request):
    security.principal_from_request(request)
    return {"ok": True, "jobs": jobs.KERNEL_JOBS}


@KERNEL.get("/catalog")
def kernel_catalog(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "blocks": list(dispatch.BLOCK_IDS),
        "contracts": [
            {
                "block": block_id,
                "path": str(dispatch.block_path(block_id)),
                "default_action": dispatch.BLOCK_DEFAULT_ACTIONS.get(block_id),
            }
            for block_id in dispatch.BLOCK_IDS
        ],
    }


@KERNEL.get("/inventory")
def kernel_inventory(request: Request):
    security.principal_from_request(request)
    absent = dispatch.missing_blocks() if dispatch.vendor_tree_present() else []
    return {
        "ok": True,
        "kernel": "CLONER",
        "lock": {
            "file": str(dispatch.LOCK_FILE),
            "vendored_root": str(dispatch.VENDOR_ROOT),
            "present_in_checkout": dispatch.vendor_tree_present(),
            "missing": absent,
        },
        "blocks": [
            {
                "block": block_id,
                "path": str(dispatch.block_path(block_id)),
                "present": block_id not in absent,
            }
            for block_id in dispatch.BLOCK_IDS
        ],
    }


@KERNEL.get("/capabilities")
def capability_roster(request: Request):
    security.optional_principal(request)
    items = []
    for item in jobs.CAPABILITIES:
        entry = dict(item)
        entry["placeholder_connectors"] = placeholders.connectors_for(item["id"])
        entry["servable"] = not bool(placeholders.missing_connectors(item["id"]))
        entry["fields"] = _field_specs(item["id"])
        entry["authority"] = ROUTE_AUTHORITY.get(item["id"]) or authority.label(3)
        items.append(entry)
    return {"ok": True, "items": items, "total": len(items)}


@KERNEL.get("/gates")
def kernel_gates(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "gates": [
            {"id": "code", "runs": "pytest -m 'not pilot'"},
            {"id": sources.PRODUCT_ID, "runs": "pytest -m pilot against the booted platform"},
            {"id": "store", "runs": "scripts/acceptance.py inside the built image"},
        ],
    }


@KERNEL.get("/ui")
def ui_manifest(request: Request):
    security.optional_principal(request)
    screens = {name: dict(spec) for name, spec in UI_SCREENS.items()}
    return {
        "ok": True,
        "ui": "app/static/index.html",
        "screens": screens,
        "total": len(screens),
        "authority": authority.label(3),
    }


@KERNEL.get("/provenance")
def kernel_provenance(request: Request):
    security.principal_from_request(request)
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "platform": config.ROOT.name,
        "blocks": [
            {"block": block_id, "path": str(dispatch.block_path(block_id))}
            for block_id in dispatch.BLOCK_IDS
        ],
        "entities": ROUTE_ENTITIES,
        "placeholders": placeholders.PLACEHOLDER_CONNECTORS,
    }
