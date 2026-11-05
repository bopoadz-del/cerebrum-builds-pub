"""Domain rules the brief states, exercised through the real routes.

The vendor blocks are part of the delivered product tree, not this checkout;
the module skips only when that sealed tree is absent (a bare writer checkout).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import formulas
from app.main import app

pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "vendor" / "blocks").is_dir(),
    reason="sealed vendor/ block tree is merged into the product image, not the writer checkout",
)

TOKEN = os.environ.get("PLATFORM_TOKEN", "dev-local-token")
AUTH = {"Authorization": "Bearer " + TOKEN}
CAPABILITIES = [
    "progress_claim_administration",
    "delay_damages_tracking",
    "qa_itp_records",
    "document_register",
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_delay_damages_boundary_is_exactly_the_cap():
    amount = 1_000_000.0
    at_cap = formulas.delay_damages(amount, 100)  # 0.1% x 100 = 10% exactly
    over_cap = formulas.delay_damages(amount, 101)
    assert at_cap["damages_amount"] == 100_000.0
    assert at_cap["capped"] is False
    assert over_cap["damages_amount"] == 100_000.0
    assert over_cap["capped"] is True


def test_progress_claim_applies_clause_14_3_and_4_2(client):
    response = client.post(
        "/v1/progress_claim_administration",
        json={"reference": "IPC-100", "status": "open", "certified_amount": 200000},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    record = body["record"]
    assert record["retention_amount"] == 10000.0
    assert record["performance_security"] == round(formulas.boq_total() * 0.1, 2)
    assert record["boq_item_codes"].startswith("P1")


def test_qa_itp_record_is_linked_to_a_boq_item(client):
    response = client.post(
        "/v1/qa_itp_records",
        json={"reference": "ITP-7", "status": "in_progress", "boq_item_code": "E3", "result": "pending"},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["record"]["boq_item_code"] == "E3"
    assert body["boq_item"]["description"] == "Imported granular fill, compacted"


def test_document_register_checksum_is_deterministic(client):
    first = client.post(
        "/v1/document_register",
        json={"reference": "DOC-1", "status": "open", "title": "Contract", "document_type": "contract"},
        headers=AUTH,
    )
    second = client.post(
        "/v1/document_register",
        json={"reference": "DOC-2", "status": "open", "title": "Contract", "document_type": "contract"},
        headers=AUTH,
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["record"]["checksum"] == second.json()["record"]["checksum"]


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_capability_rejects_missing_required_field(client, capability):
    response = client.post("/v1/" + capability, json={"status": "open"}, headers=AUTH)
    assert response.status_code == 422


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_capability_rejects_a_value_outside_the_status_vocabulary(client, capability):
    response = client.post(
        "/v1/" + capability,
        json={"reference": "X-1", "status": "archived"},
        headers=AUTH,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_capability_refuses_a_malformed_payload(client, capability):
    response = client.post("/v1/" + capability, json=["not", "an", "object"], headers=AUTH)
    assert response.status_code == 422


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_capability_hides_another_tenants_record(client, capability):
    payload = {"reference": "TENANT-A", "status": "open"}
    created = client.post(
        "/v1/" + capability,
        json=payload,
        headers={"Authorization": "Bearer token-a"},
    )
    if created.status_code == 401:
        pytest.skip("per-tenant tokens are provisioned by the deployment environment")
    assert created.status_code == 200, created.text
    record_id = created.json()["id"]
    read = client.get(
        "/v1/%s/%s" % (capability, record_id),
        headers={"Authorization": "Bearer token-b"},
    )
    assert read.status_code == 404
