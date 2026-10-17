"""PRODUCT gate: schema-sample accept + one-record round-trip. pytest -m pilot."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.schema import REQUIRED_CAPABILITY_IDS, SPECS

pytestmark = pytest.mark.pilot


def _sample_payload(capability_id: str) -> Dict[str, Any]:
    spec = SPECS[capability_id]
    body: Dict[str, Any] = {}
    for name, meta in spec["FIELDS"].items():
        constraints = spec["CONSTRAINTS"].get(name) or {}
        allowed = constraints.get("allowed_values")
        if allowed:
            body[name] = allowed[0]
        elif name == "status" or name.endswith("_status"):
            body[name] = "open"
        elif name == "channel" or name.endswith("_channel"):
            body[name] = "email"
        elif name.endswith("_at") or name.endswith("_datetime") or meta.get("type") == "datetime":
            body[name] = "2026-09-03T10:00:00"
        elif name.endswith("_date") or meta.get("type") == "date":
            body[name] = "2026-09-03"
        elif name.endswith("_time") or meta.get("type") == "time":
            body[name] = "10:00:00"
        elif "email" in name:
            body[name] = "guest@example.com"
        elif meta.get("type") in {"int", "integer", "float", "number"}:
            body[name] = constraints.get("min", 1)
        elif meta.get("type") == "bool":
            body[name] = False
        else:
            body[name] = "sample"
    return body


def test_every_capability_route_accepts_payload(client: TestClient) -> None:
    for capability_id in REQUIRED_CAPABILITY_IDS:
        payload = _sample_payload(capability_id)
        response = client.post(f"/v1/{capability_id}", json=payload)
        assert response.status_code == 200, capability_id
        body = response.json()
        assert body.get("ok") is not False, f"{capability_id} rejected a payload built from its own schema: {body}"


def test_one_record_round_trip_per_capability(client: TestClient) -> None:
    from app.store import list_all

    for capability_id in REQUIRED_CAPABILITY_IDS:
        payload = _sample_payload(capability_id)
        post = client.post(f"/v1/{capability_id}", json=payload)
        assert post.status_code == 200, capability_id
        body = post.json()
        assert body.get("ok") is not False, capability_id
        entity = SPECS[capability_id]["entity"]
        stored = list_all(entity)
        assert stored, f"{capability_id} did not remember a record they were given"
        got = client.get(f"/v1/{capability_id}")
        assert got.status_code == 200
        records = got.json().get("records") or []
        assert records, f"{capability_id} GET did not return the persisted record"
        assert any(row.get("reference") == payload["reference"] for row in records)
        if capability_id == "booking_management":
            rec = body.get("record") or {}
            assert rec.get("stay_total") == 189.0
            assert rec.get("stay_nights") == 1
            assert rec.get("actor") == "operator"
            remembered = next(
                row for row in records if row.get("reference") == payload["reference"]
            )
            assert remembered.get("stay_total") == 189.0
            assert remembered.get("nightly_rate") == 189.0


def test_health_and_ui(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    ui = client.get("/")
    assert ui.status_code == 200
    assert "Hotel Booking Platform" in ui.text
    assert "OPERATOR_TOKEN" in ui.text
    assert "Airport Operations Platform" not in ui.text
    assert "Retail Ops Tracker" not in ui.text
    assert "Veterinary Care Platform" not in ui.text
