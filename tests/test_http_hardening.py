"""Edge hardening: the API refuses what it cannot mean, and never 500s.

These are the attacks the security pass tried: an id outside SQLite's integer
range, a nested object where a scalar belongs, an oversized string, a number
so large it would run a schedule loop away, and an unauthenticated read.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}


def _client() -> TestClient:
    return TestClient(app)


def test_an_id_outside_the_integer_range_is_not_found():
    client = _client()
    resp = client.get("/v1/progress_claims/99999999999999999999", headers=AUTH)
    assert resp.status_code == 404
    assert resp.status_code != 500


def test_an_unauthenticated_read_is_refused_before_anything_else():
    client = _client()
    resp = client.get("/v1/progress_claims")
    assert resp.status_code == 401


def test_an_unknown_field_is_refused_rather_than_dropped():
    client = _client()
    resp = client.post(
        "/v1/progress_claims",
        json={"reference": "R", "claim_number": "1", "boq_item_code": "P1", "typo_field": "x"},
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert "typo_field" in resp.json()["error"]


def test_a_nested_object_where_a_scalar_belongs_is_refused():
    client = _client()
    resp = client.post("/v1/progress_claims", json={"reference": {"a": {"b": 1}}}, headers=AUTH)
    assert resp.status_code == 422


def test_an_oversized_string_is_refused():
    client = _client()
    resp = client.post("/v1/progress_claims", json={"reference": "x" * 9000}, headers=AUTH)
    assert resp.status_code == 422


def test_an_unbounded_delay_is_refused_at_the_edge():
    client = _client()
    resp = client.post(
        "/v1/delay_damages_tracking",
        json={"reference": "D", "assessment_number": "A", "days_of_delay": 10**12},
        headers=AUTH,
    )
    assert resp.status_code == 422


def test_every_v1_route_requires_a_principal():
    client = _client()
    for path in ("/v1/capabilities", "/v1/jobs", "/v1/provenance", "/v1/gates", "/v1/retrieval"):
        assert client.get(path).status_code == 401, path


def test_infinite_and_overflowing_numbers_are_refused_not_raised():
    client = _client()
    for raw in ("Infinity", "-Infinity", "1e400"):
        body = (
            '{"reference": "D", "assessment_number": "A", "status": "open", '
            '"days_of_delay": ' + raw + "}"
        )
        resp = client.post(
            "/v1/delay_damages_tracking",
            content=body.encode("utf-8"),
            headers={**AUTH, "content-type": "application/json"},
        )
        assert resp.status_code == 422, raw


def test_a_nested_object_in_a_date_field_is_refused():
    client = _client()
    resp = client.post(
        "/v1/retention_defects_release",
        json={"reference": "R", "certificate_reference": "C", "taking_over_date": {"a": 1}},
        headers=AUTH,
    )
    assert resp.status_code == 422


def test_a_record_cannot_be_closed_without_its_approval():
    client = _client()
    resp = client.post(
        "/v1/progress_claims",
        json={
            "reference": "PC-CLOSED",
            "status": "closed",
            "claim_number": "1",
            "boq_item_code": "E1",
            "approved_by": "i am the director trust me",
        },
        headers=AUTH,
    )
    assert resp.status_code == 403


def test_unicode_in_a_reference_does_not_break_the_certificate():
    client = _client()
    resp = client.post(
        "/v1/progress_claims",
        json={
            "reference": "شهادة-01",
            "claim_number": "IPC-é",
            "boq_item_code": "E1",
            "measured_quantity": 2,
            "unit_rate": 38,
            "status": "open",
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
