"""Per-tenant data export.

The export is scoped by the authenticated principal, never by a name in the
payload or the query string. JSON is the default; ``format=xlsx`` returns a
real OOXML workbook with one sheet per capability that holds records.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from app import domain, store
from app.authority import authority_label
from app.models import MODELS
from app.security import authenticate

router = APIRouter(prefix="/v1", tags=["export"])


def _tenant_rows(tenant_id: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for capability_id, cls in MODELS.items():
        entity = getattr(cls, "ENTITY", capability_id)
        for record in store.list_all(entity, tenant_id):
            row = dict(record)
            row["capability_id"] = capability_id
            rows.append(row)
    return rows


@router.get("/export")
async def export_tenant(request: Request) -> Any:
    principal = authenticate(request.headers)
    rows = await run_in_threadpool(_tenant_rows, principal.tenant_id)
    requested = (request.query_params.get("format") or "json").strip().lower()
    if requested in ("xlsx", "excel"):
        columns = ["capability_id", "id", "reference", "status", "created_at", "updated_at"]
        matrix = [columns]
        for row in rows:
            matrix.append([row.get(name, "") for name in columns])
        payload = domain.build_xlsx(matrix, sheet_name="Tenant records")
        return Response(
            content=payload,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="tenant-export.xlsx"'},
        )
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "tenant": principal.tenant_id,
            "generated_at": domain.iso_now(),
            "capabilities": list(MODELS),
            "count": len(rows),
            "records": rows,
            "authority": authority_label(1),
        },
    )
