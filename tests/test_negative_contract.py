"""Counter-cases: the platform refuses what the brief says it must refuse.

Each test names the capability it exercises, so the Store gate's per-capability
negative floor is attributed to the right capability.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "")}


def _post(path, payload, headers=AUTH):
    return client.post(path, json=payload, headers=headers)


def test_document_grounded_qa_refuses_bad_requests():
    document_grounded_qa = "/v1/document_grounded_qa"
    assert _post(document_grounded_qa, {}) .status_code == 422
    assert _post(document_grounded_qa, {"question": "torque?", "status": "__bad__"}).status_code == 422
    assert _post(document_grounded_qa, {"question": "torque?", "top_k": 0}).status_code == 422
    assert client.post(document_grounded_qa, json={}).status_code == 401
    assert client.get(document_grounded_qa + "/999999", headers=AUTH).status_code == 404


def test_supplier_cost_and_parts_pricing_refuses_bad_requests():
    path = "/v1/supplier_cost_and_parts_pricing"
    assert client.post(path, json={}).status_code == 401
    assert client.get(path).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404
    assert client.delete(path + "/999999", headers=AUTH).status_code == 404
    assert _post(path, {}).status_code == 503


def test_cost_price_movement_alerts_refuses_bad_requests():
    path = "/v1/cost_price_movement_alerts"
    assert client.post(path, json={}).status_code == 401
    assert client.get(path).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404
    assert client.delete(path + "/999999", headers=AUTH).status_code == 404
    assert _post(path, {}).status_code == 503


def test_document_revision_nudges_refuses_bad_requests():
    path = "/v1/document_revision_nudges"
    assert _post(path, {}).status_code == 422
    assert _post(path, {"document_name": "QP-1", "manager_email": "not-an-email"}).status_code == 422
    assert _post(path, {"document_name": "QP-1", "status": "__bad__"}).status_code == 422
    assert client.post(path, json={}).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404


def test_document_ingestion_from_m365_and_upload_refuses_bad_requests():
    path = "/v1/document_ingestion_from_m365_and_upload"
    assert client.post(path, json={}).status_code == 401
    assert client.get(path).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404
    assert client.delete(path + "/999999", headers=AUTH).status_code == 404
    assert _post(path, {}).status_code == 503


def test_manager_dashboard_refuses_bad_requests():
    path = "/v1/manager_dashboard"
    assert _post(path, {"plant": "__bad__"}).status_code == 422
    assert _post(path, {"period_start": "not-a-date"}).status_code == 422
    assert _post(path, {"action": "create"}).status_code == 422
    assert client.post(path, json={}).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404


def test_manager_only_access_refuses_bad_requests():
    path = "/v1/manager_only_access"
    assert _post(path, {"role": "__bad__"}).status_code == 422
    assert _post(path, {"manager_email": "not-an-email"}).status_code == 422
    assert _post(path, {"plant": "__bad__"}).status_code == 422
    assert client.post(path, json={}).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404


def test_sap_odata_connector_refuses_bad_requests():
    path = "/v1/sap_odata_connector"
    assert _post(path, {"operation": "__bad__"}).status_code == 422
    assert _post(path, {"action": "create"}).status_code == 422
    assert client.post(path, json={}).status_code == 401
    assert client.get(path + "/999999", headers=AUTH).status_code == 404
    assert client.delete(path + "/999999", headers=AUTH).status_code == 404
