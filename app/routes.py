"""The platform's HTTP surface.

Every /v1 route is authenticated, tenant-scoped, and validates a request
against the capability's own model. A successful POST persists the request
under the caller's tenant; the handler itself never persists.
"""

from __future__ import annotations

import base64
import binascii
import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import authority, contract_terms as terms, jobs, models, retrieval, store
from app.actions import _support
from app.security import require_tenant
from app.tenancy import AuthenticationError

router = APIRouter()

ROUTE_ENTITIES: Dict[str, str] = {cap: cls.ENTITY for cap, cls in models.MODELS.items()}


def _rejection(status_code: int, error: models.ValidationError) -> JSONResponse:
    payload = error.as_dict()
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={
            "X-Rejected-Field": '"%s"' % error.field,
            "X-Rejection-Reason": error.reason,
            "X-Allowed-Values": json.dumps(error.allowed),
        },
    )


def _unauthorised(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"ok": False, "error": detail, "error_kind": "unauthenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _tenant(request: Request):
    try:
        return require_tenant(request)
    except AuthenticationError as exc:  # pragma: no cover -- require_tenant raises HTTPException
        return _unauthorised(str(exc))


@router.post("/v1/rag/ingest")
async def rag_ingest(request: Request):
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001 -- any auth failure is 401
        return _unauthorised("authentication required")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    text = ""
    for key in ("text", "content", "paragraph", "document"):
        value = body.get(key) if isinstance(body, dict) else None
        if isinstance(value, str) and value.strip():
            text = value
            break
    file_name = str((body.get("file_name") or body.get("filename") or "") if isinstance(body, dict) else "")
    encoded = body.get("content_base64") if isinstance(body, dict) else None
    if not text and isinstance(encoded, str) and encoded.strip():
        try:
            raw = base64.b64decode(encoded.split(",")[-1], validate=True)
        except (binascii.Error, ValueError):
            return JSONResponse(
                status_code=422,
                content={"rejected_field": "content_base64", "rejection_reason": "wrong_format", "allowed_values": []},
            )
        try:
            text = _extract_upload_text(raw, file_name, tenant.tenant_id)
        except Exception:  # noqa: BLE001 -- an unreadable upload is a typed refusal
            return JSONResponse(
                status_code=422,
                content={"rejected_field": "content_base64", "rejection_reason": "unparseable_document", "allowed_values": []},
            )
    if not text:
        return JSONResponse(
            status_code=422,
            content={"rejected_field": "text", "rejection_reason": "missing_required", "allowed_values": []},
        )
    source = str(
        (body.get("source") if isinstance(body, dict) else "")
        or (("document:%s" % file_name) if file_name else "upload:%s" % tenant.tenant_id)
    )
    try:
        result = retrieval.ingest(tenant.tenant_id, text, source)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": str(exc), "rejected_field": "text"},
        )
    return {"ok": True, "ingested": result, "authority": authority.label_for("documents")}


def _extract_upload_text(raw: bytes, file_name: str, tenant: str) -> str:
    """Parse an uploaded document into the text the retrieval index stores."""
    import io

    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if suffix in (".xlsx", ".xlsm"):
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        try:
            lines = []
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = ["" if cell is None else str(cell) for cell in row]
                    if any(cell.strip() for cell in cells):
                        lines.append(" | ".join(cells).strip(" |"))
            return "\n".join(lines).strip()
        finally:
            workbook.close()
    return raw.decode("utf-8", errors="replace").strip()


@router.post("/v1/rag/query")
async def rag_query_post(request: Request):
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    question = ""
    for key in ("q", "query", "question"):
        value = body.get(key) if isinstance(body, dict) else None
        if isinstance(value, str) and value.strip():
            question = value
            break
    return _rag_answer(tenant.tenant_id, question)


@router.get("/v1/rag/query")
async def rag_query_get(request: Request):
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return _rag_answer(tenant.tenant_id, request.query_params.get("q") or request.query_params.get("query") or "")


def _rag_answer(tenant_id: str, question: str):
    hits = retrieval.search(tenant_id, question, top_k=5)
    return {
        "ok": True,
        "count": len(hits),
        "results": [
            {
                "source": hit["source"],
                "text": hit["text"],
                "score": hit["score"],
                "authority": authority.label_for("documents"),
            }
            for hit in hits
        ],
        "sources": retrieval.sources(tenant_id),
        "authority": authority.label_for("documents"),
    }


@router.get("/v1/jobs")
async def kernel_jobs(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {"ok": True, "jobs": jobs.JOBS}


@router.get("/v1/catalog")
async def catalog(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {
        "ok": True,
        "kernel": "COLLECTOR",
        "blocks": jobs.BLOCKS,
        "kits": jobs.KITS,
    }


@router.get("/v1/inventory")
async def inventory(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {
        "ok": True,
        "kernel": "CLONER",
        "blocks": jobs.BLOCKS,
        "lock": jobs.LOCK,
    }


@router.get("/v1/capabilities")
async def capabilities(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {"ok": True, "items": jobs.CAPABILITIES}


@router.get("/v1/gates")
async def gates(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {
        "ok": True,
        "kernel": "TESTER",
        "runs_over_http": False,
        "checks": jobs.GATE_CHECKS,
    }


@router.get("/v1/provenance")
async def provenance(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    return {
        "ok": True,
        "kernel": "STORE_MANAGER",
        "documents": [
            {"id": "document:%s" % terms.CONTRACT_FILENAME, "title": "Harbourline Civil Works contract excerpt", "clauses": sorted(terms.CLAUSES)},
            {"id": "document:%s" % terms.BOQ_FILENAME, "title": "Harbourline Civil Works bill of quantities", "items": [item["item"] for item in terms.BOQ_ITEMS]},
        ],
        "precedence": {"version": authority.PRECEDENCE_VERSION, "layers": authority.LAYERS},
    }


@router.get("/v1/formulas")
async def formulas_index(request: Request):
    try:
        require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    from app import formulas

    return {"ok": True, "formulas": formulas.catalogue(), "authority": authority.label_for("formulas")}


@router.post("/v1/{capability_id}")
async def create_record(capability_id: str, request: Request):
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    if capability_id not in models.MODELS:
        return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=422,
            content={"rejected_field": "payload", "rejection_reason": "wrong_type", "allowed_values": []},
        )
    try:
        clean = models.validate_payload(capability_id, body)
    except models.ValidationError as error:
        return _rejection(422, error)

    _support.bind_request(tenant.tenant_id, tenant.principal)
    module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))
    try:
        answer = module.handle(clean)
    except Exception as exc:  # noqa: BLE001 -- a handler failure is a typed refusal
        __import__("logging").getLogger("platform.capability").exception(
            "capability %s failed: %s", capability_id, type(exc).__name__
        )
        return {"ok": False, "error": "capability failed", "error_kind": "internal"}
    if not isinstance(answer, dict) or answer.get("ok") is False:
        return {
            "ok": False,
            "error": (answer or {}).get("error") if isinstance(answer, dict) else "handler refused",
            "result": (answer or {}).get("result") if isinstance(answer, dict) else None,
        }

    entity = ROUTE_ENTITIES[capability_id]
    try:
        stored = store.save(entity, clean, tenant_id=tenant.tenant_id)
    except Exception as exc:  # noqa: BLE001 -- persistence failure is a refusal
        __import__("logging").getLogger("platform.store").exception(
            "persistence failed for %s: %s", entity, type(exc).__name__
        )
        return {"ok": False, "error": "record could not be stored", "error_kind": "persistence"}
    return {
        "ok": True,
        "id": stored.get("id"),
        "record": stored,
        "stored": stored,
        "entity": entity,
        "result": answer.get("result"),
    }


@router.get("/v1/{capability_id}")
async def list_records(capability_id: str, request: Request):
    if capability_id not in models.MODELS:
        return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
    has_bearer = any(
        str(name).lower() == "authorization" and str(value).lower().startswith("bearer ")
        for name, value in request.headers.items()
    )
    if not has_bearer:
        # The served console may probe the catalog without a token, but it
        # sees no tenant rows until the operator connects a principal.
        return {
            "ok": True,
            "entity": ROUTE_ENTITIES[capability_id],
            "items": [],
            "total": 0,
            "requires_auth_for_records": True,
        }
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    rows = store.list_all(ROUTE_ENTITIES[capability_id], tenant_id=tenant.tenant_id)
    return {"ok": True, "entity": ROUTE_ENTITIES[capability_id], "items": rows, "total": len(rows)}


@router.get("/v1/{capability_id}/{record_id}")
async def read_record(capability_id: str, record_id: int, request: Request):
    try:
        tenant = require_tenant(request)
    except Exception:  # noqa: BLE001
        return _unauthorised("authentication required")
    if capability_id not in models.MODELS:
        return JSONResponse(status_code=404, content={"ok": False, "error": "unknown capability"})
    row = store.get(ROUTE_ENTITIES[capability_id], record_id, tenant_id=tenant.tenant_id)
    if row is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "record not found"})
    return {"ok": True, "record": row, "id": row.get("id")}
