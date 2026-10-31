"""Domain behaviour beyond the factory suites: retrieval, money and tenancy."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "")}
TENANT_A = {"Authorization": "Bearer token-a-test"}
TENANT_B = {"Authorization": "Bearer token-b-test"}


def test_rag_ingest_and_query_are_tenant_grounded(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a-test:tenant-a,token-b-test:tenant-b")
    text = "The battery pack mounting bolts are torqued to 42 Nm on line three."
    planted = client.post("/v1/rag/ingest", json={"text": text, "document_name": "WI-114"}, headers=TENANT_A)
    assert planted.status_code == 200, planted.text
    hit = client.post("/v1/rag/query", json={"q": "battery pack torque"}, headers=TENANT_A)
    assert hit.status_code == 200
    body = hit.json()
    assert body["authority"]["layer"] == 2
    assert any("42 Nm" in source["text"] for source in body["sources"])
    missing = client.post("/v1/rag/query", json={"q": "zirconium impeller"}, headers=TENANT_A)
    assert missing.status_code == 200
    assert missing.json()["sources"] == []
    other = client.post("/v1/rag/query", json={"q": "battery pack torque"}, headers=TENANT_B)
    assert other.status_code == 200
    assert other.json()["sources"] == []


def test_supplier_pricing_uses_declared_formula_and_currency(monkeypatch):
    monkeypatch.setenv("PLATFORM_TAX_RATE", "0.2")
    response = client.post(
        "/v1/supplier_cost_and_parts_pricing",
        json={
            "invoice_reference": "INV-1",
            "unit_cost_mad": 100,
            "price_mad": 150,
            "quantity": 2,
        },
        headers=AUTH,
    )
    assert response.status_code == 503  # declared SAP placeholder, refused before the handler
    from app import formulas, money_settings
    assert formulas.markup_on_cost(150, 100) == 0.5
    assert money_settings.currency() == "MAD"


def test_cross_tenant_record_is_invisible(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a-test:tenant-a,token-b-test:tenant-b")
    created = client.post("/v1/manager_only_access", json={}, headers=TENANT_A)
    assert created.status_code == 200
    record_id = created.json()["id"]
    assert client.get("/v1/manager_only_access/%s" % record_id, headers=TENANT_A).status_code == 200
    assert client.get("/v1/manager_only_access/%s" % record_id, headers=TENANT_B).status_code == 404


def test_envelope_status_vocabulary_is_enforced():
    bad = client.post("/v1/document_grounded_qa", json={"question": "q", "status": "archived"}, headers=AUTH)
    assert bad.status_code == 422
    good = client.post("/v1/document_grounded_qa", json={"question": "q", "status": "in_progress"}, headers=AUTH)
    assert good.status_code == 200
