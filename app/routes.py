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
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
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
    ui_screens,
)
from app.models import MODELS
from app.validation import validate_payload

#: Static kernel surfaces. Registered BEFORE the capability family, so
#: /v1/jobs is never read as a capability id.
KERNEL = APIRouter(prefix="/v1", tags=["kernel"], dependencies=[Depends(security.require_principal)])
#: The register's intake/search surfaces. Registered BEFORE the capability
#: family so /v1/document_register/search is not read as a record id.
INGEST = APIRouter(prefix="/v1", tags=["document-register"], dependencies=[Depends(security.require_principal)])
#: The capability family: /v1/{capability_id} and its record routes.
ROUTER = APIRouter(prefix="/v1", tags=["capabilities"], dependencies=[Depends(security.require_principal)])

#: capability -> the entity its route saves to. The entity IS the capability id
#: (the stem of its handler module), declared here so a reader never guesses.
ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in MODELS.items()}

#: capability -> the precedence layer its answer is labelled with. Source of
#: record and register answers cite the uploaded documents; claim, delay and
#: QA answers are computed from the cited clauses; access decisions are
#: certified policy. The label travels on every answer, not only on create.
ROUTE_AUTHORITY: Dict[str, str] = {
    "contract_and_boq_source_of_record": authority.label(2),
    "progress_claims_and_payment_certificates": authority.label(3),
    "delay_damages_tracking": authority.label(3),
    "qa_itp_records": authority.label(3),
    "document_register": authority.label(2),
    "claim_review_and_dispute_resolution": authority.label(2),
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


def _refusal(result: Dict[str, Any]) -> JSONResponse:
    kind = str(result.get("error_kind") or "refused")
    body = {
        "ok": False,
        "error": str(result.get("error") or "the capability refused"),
        "error_kind": kind,
    }
    if result.get("blocks"):
        body["blocks"] = result["blocks"]
    if result.get("blocks_unavailable"):
        body["blocks_unavailable"] = result["blocks_unavailable"]
    return JSONResponse(status_code=200, content=body)


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
        "authority": result.get("authority") or ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
        "tenant_id": principal.tenant_id,
    }
    if result.get("result", {}).get("blocks_unavailable"):
        body["blocks_unavailable"] = result["result"]["blocks_unavailable"]
    return JSONResponse(status_code=200, content=body)


@ROUTER.post("/{capability_id}")
def create_capability_record(capability_id: str, request: Request, payload: Optional[Dict[str, Any]] = None):
    principal = security.principal_from_request(request)
    return _create(capability_id, dict(payload or {}), principal)


@ROUTER.get("/{capability_id}")
def list_capability_records(capability_id: str, request: Request):
    principal = security.principal_from_request(request)
    model = MODELS.get(capability_id)
    if model is None:
        raise security.not_found("capability")
    items = store.list_all(model.ENTITY, tenant_id=principal.tenant_id)
    return {
        "ok": True,
        "capability_id": capability_id,
        "entity": model.ENTITY,
        "items": items,
        "total": len(items),
        "authority": ROUTE_AUTHORITY.get(capability_id) or authority.label(3),
    }


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
def update_capability_record(capability_id: str, item_id: str, payload: Dict[str, Any], request: Request):
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


# --- document register: intake, search and retrieval -----------------------


INTAKE_GUIDE = {
    "ok": True,
    "capability_id": "document_register",
    "intake": "POST a multipart file (PDF, XLSX, CSV or text) to this path",
    "search": "GET /v1/document_register/search?q=<terms>",
    "ask": "POST {\"question\": \"<question>\"} to /v1/document_register/ask",
    "authority": ROUTE_AUTHORITY.get("document_register") or authority.label(2),
}


@INGEST.get("/document_register/intake")
def intake_guide(request: Request):
    security.principal_from_request(request)
    return dict(INTAKE_GUIDE)


@INGEST.get("/document_register/ask")
def ask_guide(request: Request):
    security.principal_from_request(request)
    return dict(INTAKE_GUIDE)


#: An uploaded controlled copy is bounded: a project document is not larger
#: than this, and an unbounded read lets a caller fill the storage root.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@INGEST.post("/document_register/intake")
def intake_document(request: Request, file: UploadFile = File(...)):
    """Parse an uploaded document and register it as a controlled copy.

    The parsed text is kept under the one storage root and keyed by the
    register entry's own checksum, so a later question is answered from the
    document this tenant actually attached, never from a guess.
    """
    principal = security.principal_from_request(request)
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    filename = file.filename or "upload"
    if len(data) > MAX_UPLOAD_BYTES:
        return _rejection(
            {
                "field": "file",
                "reason": "too_large",
                "message": f"the uploaded file exceeds {MAX_UPLOAD_BYTES} bytes",
            }
        )
    if not data:
        return _rejection(
            {
                "field": "file",
                "reason": "empty_file",
                "message": "the uploaded file is empty",
            }
        )
    parsed = document_intake.parse_document(filename, data)
    if not parsed["text"].strip():
        return _rejection(
            {
                "field": "file",
                "reason": "no_extractable_text",
                "message": "the uploaded file carries no extractable text",
            }
        )
    from app import capability_support

    citation = f"document:{filename}"
    revision = "A"
    controlled = {
        "reference": parsed["reference"],
        "title": parsed["title"],
        "document_type": parsed["document_type"],
        "revision": revision,
        "source_document": citation,
    }
    payload = {
        **controlled,
        "checksum": capability_support.digest(controlled),
        "status": "open",
    }
    response = _create("document_register", payload, principal)
    body = json.loads(response.body)
    if response.status_code != status.HTTP_200_OK or body.get("ok") is not True:
        return response
    text_file = document_intake.keep_text(
        principal.tenant_id, payload["checksum"], parsed["text"]
    )
    body["parsed"] = True
    body["intake"] = {
        "filename": filename,
        "characters": parsed["characters"],
        "lines": parsed["lines"],
        "document_type": parsed["document_type"],
        "text_file": text_file,
        "excerpt": parsed["text"][:280],
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=body)


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
    principal = security.principal_from_request(request)
    question = str((payload or {}).get("question") or "").strip()
    if not question:
        return _rejection(
            {
                "field": "question",
                "reason": "missing_required",
                "message": "a question is required",
            }
        )
    found = document_intake.answer(principal.tenant_id, question)
    if found.get("ok") is not True:
        # The contract and BOQ are the platform's own source of record; an
        # answer can still cite them when the tenant has attached nothing yet.
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


# --- kernel surfaces -------------------------------------------------------


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
    absent = dispatch.missing_blocks()
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
            {"block": block_id, "path": str(dispatch.block_path(block_id)), "present": block_id not in absent}
            for block_id in dispatch.BLOCK_IDS
        ],
    }


@KERNEL.get("/capabilities")
def capability_roster(request: Request):
    security.principal_from_request(request)
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
    security.principal_from_request(request)
    screens = ui_screens()
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
        "blocks": [{"block": block_id, "path": str(dispatch.block_path(block_id))} for block_id in dispatch.BLOCK_IDS],
        "entities": ROUTE_ENTITIES,
        "placeholders": placeholders.PLACEHOLDER_CONNECTORS,
    }
