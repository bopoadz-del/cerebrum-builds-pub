"""The bill is the ceiling on a certificate, and the dashboard reads the store.

A progress claim certifies the work actually measured at the BOQ's rate; it
does not certify a whole BOQ line because a certificate names it, and it does
not let a caller-entered rate overwrite the source of record. The portfolio
dashboard reports the tenant's stored position rather than a typed total.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}

BOQ_TEXT = (
    "# Earthworks\n"
    "Item\tDescription\tUnit\tQty\tRate (SAR)\n"
    "E1\tBulk excavation to reduced level\tm3\t12500\t38\n"
)


def _tenant(monkeypatch, name: str) -> dict:
    """A fresh tenant with its own token, through the declared mechanism."""
    token = "tok-" + name + "-" + os.urandom(6).hex()
    existing = os.environ.get("TENANT_TOKENS", "")
    monkeypatch.setenv("TENANT_TOKENS", (existing + "," if existing else "") + token + ":" + name)
    return {"Authorization": "Bearer " + token}


def _claim(client, headers, reference, measured, rate=999.0):
    return client.post(
        "/v1/progress_claims",
        headers=headers,
        json={
            "reference": reference,
            "status": "open",
            "ipc_number": reference,
            "boq_item": "E1",
            "measured_quantity": measured,
            "boq_rate": rate,
            "source_text": BOQ_TEXT,
        },
    )


def test_certificate_uses_measured_quantity_at_the_boq_rate(client: TestClient):
    resp = _claim(client, AUTH, "ipc-measured-1", 100.0)
    assert resp.status_code == 200, resp.text[:200]
    body = resp.json()
    assert body.get("ok") is True, body
    computed = body["computed"]
    assert computed["measured_quantity"] == 100.0
    assert computed["gross_measured"] == 3800.0, "the bill's rate (38) governs, not the caller's 999"
    assert computed["boq_quantity"] == 12500.0


def test_certificate_refuses_more_than_the_bill_allows(client: TestClient):
    before = len(client.get("/v1/progress_claims", headers=AUTH).json().get("items") or [])
    resp = _claim(client, AUTH, "ipc-over-measured", 13000.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is False, "a measurement beyond the BOQ quantity must be refused"
    assert "exceeds the BOQ quantity" in str(body.get("error") or "")
    after = len(client.get("/v1/progress_claims", headers=AUTH).json().get("items") or [])
    assert after == before, "a refused certificate must not be persisted"


def test_dashboard_reads_the_stored_contract_position(client: TestClient, monkeypatch):
    headers = _tenant(monkeypatch, "portfolio-tenant")
    for reference, measured in (("ipc-p1", 100.0), ("ipc-p2", 200.0)):
        made = _claim(client, headers, reference, measured)
        assert made.status_code == 200 and made.json().get("ok") is True, made.text[:200]

    resp = client.post(
        "/v1/claims_analytics_dashboard",
        headers=headers,
        json={
            "reference": "position-1",
            "status": "open",
            "period": "2026-11",
            "boq_source_text": BOQ_TEXT,
        },
    )
    assert resp.status_code == 200, resp.text[:200]
    body = resp.json()
    assert body.get("ok") is True, body
    computed = body["computed"]
    assert computed["certified_to_date"] == 11400.0, computed
    assert computed["retention_total"] == 570.0, computed
    assert computed["boq_value"] == 475000.0, computed
    assert computed["certified_vs_boq_ratio"] == round(11400.0 / 475000.0, 4)
    assert computed["sources"]["progress_claims"] == 2
    assert computed["average_claim"] == 5700.0
