"""Counter-cases for every capability: the platform refuses the wrong thing.

Each test names the capability it exercises, states a rule from the brief
(a vocabulary, a bound, a tenancy boundary) and asserts the platform's
refusal. None of these assert a happy path.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}
OTHER = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN_B", "dev-local-token-b")}


def _sample(capability_id):
    from app.models import MODELS

    return MODELS[capability_id].sample()


def _missing_reference_refused(path):
    resp = client.post(path, json={}, headers=AUTH)
    assert resp.status_code == 422
    return resp


def _create(path, payload):
    return client.post(path, json=payload, headers=AUTH)


def test_contract_and_boq_source_of_record_refuses_unknown_terms():
    path = "/v1/contract_and_boq_source_of_record"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**_sample("contract_and_boq_source_of_record"), "document_type": "not-a-document"}).status_code == 422
    assert _create(path, {**_sample("contract_and_boq_source_of_record"), "clause_ref": "99.9"}).status_code == 422
    assert _create(path, {**_sample("contract_and_boq_source_of_record"), "boq_item": "Z9"}).status_code == 422
    created = _create(path, {"reference": "negative-source", "document_type": "contract"})
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404


def test_progress_claims_and_payment_certificates_refuses_invalid_claims():
    path = "/v1/progress_claims_and_payment_certificates"
    base = {"reference": "negative-ipc"}
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**base, "claimed_quantity": -1}).status_code == 422
    assert _create(path, {**base, "boq_item": "Z9"}).status_code == 422
    assert _create(path, {**base, "retention_pct": 101}).status_code == 422
    created = _create(path, dict(base))
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.get(f"{path}/999999", headers=AUTH).status_code == 404


def test_delay_damages_tracking_refuses_invalid_dates_and_bounds():
    path = "/v1/delay_damages_tracking"
    base = {"reference": "negative-delay"}
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**base, "delay_days": -1}).status_code == 422
    assert _create(path, {**base, "daily_rate_pct": 101}).status_code == 422
    assert _create(path, {**base, "assessment_date": "not-a-date"}).status_code == 422
    created = _create(path, dict(base))
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.get(f"{path}/999999", headers=AUTH).status_code == 404


def test_qa_itp_records_refuses_unknown_items_and_results():
    path = "/v1/qa_itp_records"
    base = {"reference": "negative-itp"}
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**base, "boq_item": "Z9"}).status_code == 422
    assert _create(path, {**base, "test_result": "probably"}).status_code == 422
    assert _create(path, {**base, "inspection_date": "03/09/2026"}).status_code == 422
    refused = _create(path, {**base, "defect_close_out_date": "2026-09-03"})
    assert refused.status_code == 200 and refused.json().get("ok") is False
    created = _create(path, dict(base))
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404


def test_document_register_refuses_invalid_types_and_missing_reference():
    path = "/v1/document_register"
    base = {"reference": "negative-register"}
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**base, "document_type": "invented"}).status_code == 422
    created = _create(path, {**base, "document_type": "contract"})
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.get(f"{path}/999999", headers=AUTH).status_code == 404


def test_claim_review_and_dispute_resolution_refuses_bad_determinations():
    path = "/v1/claim_review_and_dispute_resolution"
    base = {"reference": "negative-review"}
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    assert _create(path, {**base, "determination": "awarded"}).status_code == 422
    assert _create(path, {**base, "claimed_value": -5}).status_code == 422
    refused = _create(
        path,
        {**base, "claimed_value": 100, "determined_value": 150, "determination": "accepted", "basis": "measured"},
    )
    assert refused.status_code == 200 and refused.json().get("ok") is False
    decided = _create(path, {**base, "claimed_value": 100, "determination": "accepted"})
    assert decided.status_code == 200 and decided.json().get("ok") is False
    created = _create(path, dict(base))
    assert created.status_code == 200
    record_id = created.json()["stored"]["id"]
    assert client.get(f"{path}/{record_id}", headers=OTHER).status_code == 404
    assert client.delete(f"{path}/{record_id}", headers=OTHER).status_code == 404


def test_missing_reference_is_refused_on_every_capability():
    for capability_id in (
        "contract_and_boq_source_of_record",
        "progress_claims_and_payment_certificates",
        "delay_damages_tracking",
        "qa_itp_records",
        "document_register",
        "claim_review_and_dispute_resolution",
    ):
        _missing_reference_refused("/v1/" + capability_id)
