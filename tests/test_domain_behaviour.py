"""The domain decisions the brief asks for, performed through the live routes.

Every expected figure is derived from the uploaded source of record through
the product's own data module, never typed here as a magic number: the tests
check the relationship (quantity x rate, percentage retention, capped daily
fee) the contract states.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app import contract_data, formulas
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}


def _post(path, payload):
    response = client.post(path, json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True, body
    return body


def test_source_of_record_values_a_boq_line_from_the_document():
    line = contract_data.boq_lines()[0]
    body = _post(
        "/v1/contract_and_boq_source_of_record",
        {"reference": "behaviour-source", "document_type": "boq", "boq_item": line["item"]},
    )
    result = body["result"]
    assert result["quantity"] == line["quantity"]
    assert result["rate"] == line["rate"]
    assert result["amount"] == round(line["quantity"] * line["rate"], 2)
    assert result["citation"] == contract_data.BOQ_DOCUMENT
    assert "layer 2" in body["authority"]


def test_progress_claim_applies_retention_and_carries_quantity_forward():
    line = contract_data.boq_lines()[0]
    claimed = max(1.0, float(line["quantity"]) / 2.0)
    body = _post(
        "/v1/progress_claims_and_payment_certificates",
        {
            "reference": "behaviour-ipc",
            "boq_item": line["item"],
            "claimed_quantity": claimed,
        },
    )
    result = body["result"]
    gross = round(claimed * float(line["rate"]), 2)
    retention = formulas.retention_amount(gross, contract_data.RETENTION_PCT)
    assert result["gross_amount"] == gross
    assert result["retention_amount"] == retention
    assert result["net_certified"] == round(gross - retention, 2)
    assert result["carried_forward_quantity"] == round(float(line["quantity"]) - claimed, 2)
    assert result["release_at_taking_over"] + result["release_at_dnp_end"] == retention


def test_delay_damages_are_capped_at_the_contractual_percentage():
    accepted = contract_data.boq_total()
    body = _post(
        "/v1/delay_damages_tracking",
        {
            "reference": "behaviour-delay",
            "accepted_contract_amount": accepted,
            "delay_days": 2000,
            "extension_days": 0,
        },
    )
    result = body["result"]
    expected = formulas.delay_damages(
        accepted,
        contract_data.DELAY_DAMAGES_DAILY_PCT,
        2000,
        contract_data.DELAY_DAMAGES_CAP_PCT,
    )
    assert result["delay_damages"] == expected["damages"]
    assert result["damages_cap"] == expected["cap"]
    assert result["cap_reached"] is True


def test_qa_itp_accepts_only_a_passing_test_and_measures_dnp_from_taking_over():
    body = _post(
        "/v1/qa_itp_records",
        {
            "reference": "behaviour-itp",
            "test_result": "fail",
            "taking_over_date": "2026-09-03",
        },
    )
    result = body["result"]
    assert result["accepted"] is False
    assert result["defects_notification_end"] == "2027-09-03"


def test_document_register_checksums_its_controlled_copy():
    body = _post(
        "/v1/document_register",
        {"reference": "behaviour-register", "document_type": "contract", "title": contract_data.CONTRACT_DOCUMENT},
    )
    result = body["result"]
    assert result["checksum"]
    assert result["checksum_matches"] is True
    assert result["source_document"] == contract_data.CONTRACT_DOCUMENT


def test_document_register_reports_a_checksum_that_does_not_match():
    body = _post(
        "/v1/document_register",
        {
            "reference": "behaviour-register-mismatch",
            "document_type": "contract",
            "title": contract_data.CONTRACT_DOCUMENT,
            "checksum": "0" * 64,
        },
    )
    result = body["result"]
    assert result["checksum_matches"] is False
    assert result["checksum"]


def test_claim_review_records_a_basis_bound_determination():
    body = _post(
        "/v1/claim_review_and_dispute_resolution",
        {
            "reference": "behaviour-review",
            "claimed_value": 1000,
            "determined_value": 600,
            "determination": "reduced",
            "basis": "remeasured quantity against the BOQ",
        },
    )
    result = body["result"]
    assert result["determination"] == "reduced"
    assert result["determined_value"] == 600
    assert result["basis"] == "remeasured quantity against the BOQ"


def test_progress_claim_without_a_measured_quantity_carries_nothing_forward():
    """A certificate for the whole line cannot also carry the whole line
    forward as uncertified: gross and carried-forward agree on one quantity."""
    line = contract_data.boq_lines()[0]
    body = _post(
        "/v1/progress_claims_and_payment_certificates",
        {"reference": "behaviour-ipc-full", "boq_item": line["item"]},
    )
    result = body["result"]
    assert result["claimed_quantity"] == float(line["quantity"])
    assert result["gross_amount"] == round(float(line["quantity"]) * float(line["rate"]), 2)
    assert result["carried_forward_quantity"] == 0.0


def test_claim_review_refuses_a_rejected_determination_that_awards_money():
    response = client.post(
        "/v1/claim_review_and_dispute_resolution",
        json={
            "reference": "behaviour-review-contradiction",
            "claimed_value": 1000,
            "determined_value": 50,
            "determination": "rejected",
            "basis": "no entitlement",
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("ok") is False
    assert body.get("error_kind") == "determination_contradicts_value"


def test_document_register_revisions_are_distinct_versions():
    first = _post(
        "/v1/document_register",
        {"reference": "behaviour-revision", "document_type": "contract", "revision": "A"},
    )["result"]
    second = _post(
        "/v1/document_register",
        {"reference": "behaviour-revision", "document_type": "contract", "revision": "B"},
    )["result"]
    assert first["semver"] != second["semver"]
    assert first["revision_key"] != second["revision_key"]
