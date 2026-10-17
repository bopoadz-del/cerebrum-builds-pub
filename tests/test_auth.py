"""Fail-closed bearer secrets, operator gate, CORS allowlist."""

from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.not_pilot

SCHEMA_SAMPLE = {
    "reference": "sample",
    "status": "open",
    "stay_kind": "night",
    "room_label": "sample",
}


def test_mutating_route_without_token_is_401(anon_client: TestClient) -> None:
    response = anon_client.post("/v1/booking_management", json=SCHEMA_SAMPLE)
    assert response.status_code == 401


def test_mutating_route_with_invalid_token_is_401(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/v1/booking_management",
        json=SCHEMA_SAMPLE,
        headers={"Authorization": "Bearer not-the-operator-secret"},
    )
    assert response.status_code == 401


def test_placeholder_secret_is_not_accepted(
    isolated_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPERATOR_TOKEN", "changeme")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    from app.main import app

    with TestClient(app) as client:
        denied = client.post(
            "/v1/booking_management",
            json=SCHEMA_SAMPLE,
            headers={"Authorization": "Bearer changeme"},
        )
        assert denied.status_code == 401


def test_unconfigured_secret_fail_closed(
    isolated_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPERATOR_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    from app.main import app

    with TestClient(app) as client:
        denied = client.post("/v1/booking_management", json=SCHEMA_SAMPLE)
        assert denied.status_code == 401
        assert "not configured" in denied.json().get("detail", "")


def test_rag_ingest_without_token_is_401(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/v1/rag/ingest",
        json={"layer": 1, "doc_id": "x", "title": "t", "text": "hotel occupancy peak season"},
    )
    assert response.status_code == 401


def test_admin_export_requires_matching_secret(anon_client: TestClient) -> None:
    missing = anon_client.get("/v1/admin/export")
    assert missing.status_code == 401
    present_only = anon_client.get(
        "/v1/admin/export", headers={"Authorization": f"Bearer unmatched-{secrets.token_hex(16)}"}
    )
    assert present_only.status_code == 401


def test_operator_token_attributes_actor(client: TestClient) -> None:
    response = client.post("/v1/booking_management", json=SCHEMA_SAMPLE)
    assert response.status_code == 200
    body = response.json()
    assert body.get("ok") is not False
    assert body.get("actor") == "operator"
    assert body.get("actor_role") == "operator"
    rec = body.get("record") or {}
    assert rec.get("actor") == "operator"
    assert rec.get("actor_role") == "operator"
    assert rec.get("stay_total") == 189.0
    assert rec.get("stay_nights") == 1
    assert rec.get("claimed_actor") is None


def test_forged_actor_is_claimed_only(client: TestClient) -> None:
    forged = {**SCHEMA_SAMPLE, "actor": "forged-hotel-admin", "user_id": "spoof"}
    response = client.post("/v1/booking_management", json=forged)
    assert response.status_code == 200
    rec = response.json().get("record") or {}
    assert rec.get("actor") == "operator"
    assert rec.get("actor_role") == "operator"
    assert rec.get("claimed_actor") == "forged-hotel-admin"
    assert rec.get("user_id") != "spoof"
    assert rec.get("user_id") == "operator"


def test_cors_allowlist_refuses_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWLIST", "*,https://desk.example")
    from app.auth import cors_allowlist

    assert cors_allowlist() == ["https://desk.example"]
    monkeypatch.setenv("CORS_ALLOWLIST", "")
    assert cors_allowlist() == []
