"""Kernel roster, catalog, inventory, capability discovery, tracks, formulas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import formulas, track_schema
from app.authority import authority_label
from app.models import MODELS
from app.security import authenticate
from app.version_info import VERSION

router = APIRouter(prefix="/v1", tags=["kernel"])

ROOT = Path(__file__).resolve().parents[2]

JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store registry and bind the blocks this product composes.",
        "http_routes": ["/v1/catalog"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Load every locked block from its pinned vendor path.",
        "http_routes": ["/v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author the capability handlers, routes, schema and UI.",
        "http_routes": ["/v1/capabilities"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the code, product and Store acceptance gates.",
        "http_routes": ["/v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Register provenance for the delivered package.",
        "http_routes": ["/v1/provenance"],
        "agent": "store_manager",
    },
]


@router.get("/jobs")
async def jobs(request: Request) -> Any:
    authenticate(request.headers)
    return JSONResponse(status_code=200, content={"ok": True, "jobs": JOBS, "authority": authority_label(1)})


@router.get("/catalog")
async def catalog(request: Request) -> Any:
    authenticate(request.headers)
    kits = []
    kits_dir = ROOT / "kits"
    if kits_dir.is_dir():
        for manifest in sorted(kits_dir.glob("*/manifest.json")):
            try:
                kits.append(json.loads(manifest.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return JSONResponse(
        status_code=200,
        content={"ok": True, "kernel": "COLLECTOR", "kits": kits, "blocks": sorted(_locked_blocks())},
    )


def _locked_blocks() -> List[str]:
    try:
        data = json.loads((ROOT / "blocks.lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    blocks = data.get("blocks") or data
    return sorted(blocks.keys()) if isinstance(blocks, dict) else []


@router.get("/inventory")
async def inventory(request: Request) -> Any:
    authenticate(request.headers)
    lock_path = ROOT / "blocks.lock.json"
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "kernel": "CLONER",
            "lock": "blocks.lock.json",
            "lock_present": lock_path.is_file(),
            "blocks": _locked_blocks(),
        },
    )


@router.get("/capabilities")
async def capabilities(request: Request) -> Any:
    authenticate(request.headers)
    items = [
        {
            "id": capability_id,
            "entity": getattr(cls, "ENTITY", capability_id),
            "fields": list(getattr(cls, "FIELDS", [])),
            "constraints": getattr(cls, "CONSTRAINTS", {}),
            "route": "/v1/" + capability_id,
        }
        for capability_id, cls in MODELS.items()
    ]
    return JSONResponse(
        status_code=200,
        content={"ok": True, "items": items, "total": len(items), "authority": authority_label(1)},
    )


@router.get("/tracks")
async def tracks(request: Request) -> Any:
    """The validated track catalogue: ids, versions, weights, terms."""
    authenticate(request.headers)
    try:
        entries = track_schema.index()
        error = ""
    except track_schema.TrackError as exc:
        entries, error = [], str(exc)
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "tracks": entries,
            "total": len(entries),
            "error": error,
            "authorship": "customer_yaml",
            "authority": authority_label(1),
        },
    )


@router.get("/formulas")
async def formula_roster(request: Request) -> Any:
    """The arithmetic this platform reaches, and where each number comes from."""
    authenticate(request.headers)
    return JSONResponse(
        status_code=200,
        content={"ok": True, **formulas.describe(), "authority": authority_label(3)},
    )


@router.get("/gates")
async def gates(request: Request) -> Any:
    authenticate(request.headers)
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "kernel": "TESTER",
            "runs_over_http": False,
            "gates": ["code", "product", "store"],
            "build_level": "production",
            "version": VERSION,
        },
    )


@router.get("/provenance")
async def provenance(request: Request) -> Any:
    authenticate(request.headers)
    path = ROOT / "docs" / "provenance" / "provenance.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    return JSONResponse(
        status_code=200,
        content={"ok": True, "kernel": "STORE_MANAGER", "provenance": payload, "authority": authority_label(1)},
    )
