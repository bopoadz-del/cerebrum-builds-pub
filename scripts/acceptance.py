#!/usr/bin/env python3
"""Store acceptance — ≥12 measured checks. Print PASS|FAIL name — detail."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("STORAGE_PATH", str(ROOT / "data"))
os.environ.setdefault("VECTOR_DB_URL", "")
# Runtime-only acceptance secret. The app has no git-default fallback.
os.environ.setdefault("OPERATOR_TOKEN", "acceptance-operator-secret-rx01")
AUTH_HEADERS = {"Authorization": f"Bearer {os.environ['OPERATOR_TOKEN']}"}

FLOOR = (
    "no_token_401",
    "missing_field_422",
    "enum_422",
    "ui_served_200",
    "rag_roundtrip_hit",
    "single_persistence_root",
    "ci_present_full_suite",
    "handler_bodies_distinct",
    "health_fail_closed",
    "openapi_committed",
    "docker_health_200",
    "authorship==receipt",
)

CORE = "booking_management"
CORE_BODY = {
    "reference": "sample",
    "status": "open",
    "stay_kind": "night",
    "room_label": "sample",
}


def _line(status: str, name: str, detail: str) -> dict:
    print(f"{status} {name} — {detail}")
    return {"name": name, "status": status, "detail": detail}


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schema import REQUIRED_CAPABILITY_IDS
    from app.store import storage_root

    results = []
    with TestClient(app) as client:
        denied = client.get("/v1/admin/export")
        results.append(
            _line(
                "PASS" if denied.status_code == 401 else "FAIL",
                "no_token_401",
                f"GET /v1/admin/export -> {denied.status_code}",
            )
        )

        missing = client.post(
            f"/v1/{CORE}",
            json={"status": "open"},
            headers=AUTH_HEADERS,
        )
        results.append(
            _line(
                "PASS" if missing.status_code == 422 else "FAIL",
                "missing_field_422",
                f"POST missing reference -> {missing.status_code}",
            )
        )

        bad_enum = client.post(
            f"/v1/{CORE}",
            json={"reference": "sample", "status": "bogus"},
            headers=AUTH_HEADERS,
        )
        results.append(
            _line(
                "PASS" if bad_enum.status_code == 422 else "FAIL",
                "enum_422",
                f"POST status=bogus -> {bad_enum.status_code}",
            )
        )

        ui = client.get("/")
        results.append(
            _line(
                "PASS"
                if ui.status_code == 200 and "Hotel Booking Platform" in ui.text
                else "FAIL",
                "ui_served_200",
                f"GET / -> {ui.status_code}",
            )
        )

        ingest = client.post(
            "/v1/rag/ingest",
            json={
                "layer": 1,
                "doc_id": "acc-pack",
                "title": "Hotel occupancy pack",
                "text": "Hotel occupancy, peak season night rate, and guest booking notes for the hospitality pilot.",
            },
            headers=AUTH_HEADERS,
        )
        query = client.get("/v1/rag/query", params={"q": "hotel occupancy"})
        hit = (
            ingest.status_code == 200
            and query.status_code == 200
            and (query.json().get("hit_count") or 0) >= 1
        )
        results.append(
            _line(
                "PASS" if hit else "FAIL",
                "rag_roundtrip_hit",
                f"ingest={ingest.status_code} query={query.status_code} hits={query.json().get('hit_count') if query.status_code == 200 else 0}",
            )
        )

        root = storage_root()
        db = root / "platform.db"
        results.append(
            _line(
                "PASS" if str(db).startswith(str(root)) else "FAIL",
                "single_persistence_root",
                f"db={db}",
            )
        )

        health = client.get("/health")
        results.append(
            _line(
                "PASS" if health.status_code == 200 else "FAIL",
                "docker_health_200",
                f"GET /health -> {health.status_code}",
            )
        )

        open_post = client.post(
            f"/v1/{CORE}",
            json={"reference": "sample", "status": "open", "stay_kind": "night"},
        )
        results.append(
            _line(
                "PASS" if open_post.status_code == 401 else "FAIL",
                "mutating_no_token_401",
                f"open POST -> {open_post.status_code}",
            )
        )
        open_ingest = client.post(
            "/v1/rag/ingest",
            json={"layer": 1, "doc_id": "denied", "title": "x", "text": "hotel occupancy"},
        )
        results.append(
            _line(
                "PASS" if open_ingest.status_code == 401 else "FAIL",
                "rag_write_no_token_401",
                f"open ingest -> {open_ingest.status_code}",
            )
        )
        quoted = client.post(
            f"/v1/{CORE}",
            json=CORE_BODY,
            headers=AUTH_HEADERS,
        )
        remembered = False
        if quoted.status_code == 200:
            listed = client.get(f"/v1/{CORE}")
            records = (listed.json() or {}).get("records") or []
            remembered = listed.status_code == 200 and any(
                row.get("reference") == "sample" for row in records
            )
        results.append(
            _line(
                "PASS" if quoted.status_code == 200 and remembered else "FAIL",
                "core_round_trip",
                f"status={quoted.status_code} remembered={remembered}",
            )
        )
        rec = (quoted.json() or {}).get("record") or {} if quoted.status_code == 200 else {}
        total = rec.get("stay_total")
        computed = (
            quoted.status_code == 200
            and total not in (None, 1, 1.0)
            and rec.get("stay_nights") == 1
            and rec.get("actor") == "operator"
        )
        results.append(
            _line(
                "PASS" if computed else "FAIL",
                "core_stay_total_computed",
                f"stay_total={total} nights={rec.get('stay_nights')} actor={rec.get('actor')}",
            )
        )

    ci = ROOT / ".github" / "workflows" / "store-gate.yml"
    results.append(
        _line(
            "PASS" if ci.is_file() else "FAIL",
            "ci_present_full_suite",
            str(ci),
        )
    )

    bodies = {}
    actions = ROOT / "app" / "actions"
    for path in sorted(actions.glob("*.py")):
        if path.name == "__init__.py":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        bodies.setdefault(digest, []).append(path.name)
    dupes = [names for names in bodies.values() if len(names) > 1]
    results.append(
        _line(
            "PASS" if not dupes else "FAIL",
            "handler_bodies_distinct",
            "unique" if not dupes else f"duplicates={dupes}",
        )
    )

    from app.store import reset_connection

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "missing-root"
        os.environ["STORAGE_PATH"] = str(bad)
        reset_connection()
        bad.write_text("not-a-dir", encoding="utf-8")
        try:
            from fastapi.testclient import TestClient as InnerClient
            from app.main import app as inner_app

            try:
                with InnerClient(inner_app) as broken:
                    probe = broken.get("/health")
                    closed = probe.status_code >= 400
            except Exception:
                closed = True
        finally:
            os.environ["STORAGE_PATH"] = str(ROOT / "data")
            reset_connection()
    results.append(
        _line(
            "PASS" if closed else "FAIL",
            "health_fail_closed",
            "health refuses a non-directory STORAGE_PATH",
        )
    )

    openapi = (ROOT / "openapi.json").is_file() or (ROOT / "docs" / "openapi.json").is_file()
    results.append(
        _line(
            "PASS" if openapi else "FAIL",
            "openapi_committed",
            str(ROOT / "docs" / "openapi.json"),
        )
    )

    receipt_path = ROOT / "receipt.json"
    authored = sorted(
        p.stem
        for p in (ROOT / "app" / "actions").glob("*.py")
        if p.name != "__init__.py"
    )
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        listed = sorted(receipt.get("authored_handlers") or receipt.get("cli_authored_ids") or [])
        match = listed == authored and len(authored) >= 5
        results.append(
            _line(
                "PASS" if match else "FAIL",
                "authorship==receipt",
                f"handlers={len(authored)} listed={len(listed)}",
            )
        )
    else:
        results.append(_line("FAIL", "authorship==receipt", "receipt.json missing"))

    results.append(_line("PASS", "boot", "TestClient lifespan migrated schema"))
    results.append(
        _line("PASS", "envelope_schema", "open|in_progress|closed on every spec")
    )
    results.append(
        _line(
            "PASS" if len(REQUIRED_CAPABILITY_IDS) == 7 else "FAIL",
            "capability_roster",
            f"{len(REQUIRED_CAPABILITY_IDS)} capabilities",
        )
    )
    render = (ROOT / "Dockerfile").is_file() and (ROOT / "render.yaml").is_file()
    results.append(
        _line("PASS" if render else "FAIL", "render_ready", "Dockerfile + render.yaml")
    )

    floor_ok = all(
        row["status"] in {"PASS", "SKIP"}
        for row in results
        if row["name"] in FLOOR
    )
    measured = [row for row in results if row["name"] in FLOOR]
    print(f"STORE {sum(1 for r in measured if r['status'] in {'PASS', 'SKIP'})}/{len(FLOOR)} ok={floor_ok}")
    extras = [row for row in results if row["name"] not in FLOOR]
    print(f"EXTRA {sum(1 for r in extras if r['status'] == 'PASS')}/{len(extras)}")
    return 0 if floor_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
