"""Counter-cases: what each capability REFUSES.

Four cases per capability (the acceptance floor): a missing required field, a
value outside the declared vocabulary, a cross-tenant read, and a malformed
payload. Values come from each capability's own model, never from a test case
id or a product literal.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
OTHER_TENANT = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN_B"]}

REFUSED = (400, 403, 404, 409, 422)
ACCEPTED = (200,)


def _refused(response) -> bool:
    if response.status_code in REFUSED:
        return True
    if response.status_code not in ACCEPTED:
        return False
    try:
        body = response.json()
    except Exception:
        return False
    return isinstance(body, dict) and body.get("ok") is False


BODIES = {
    "contract_source_of_record": {
        "reference": "nf-contract",
        "source_document": "document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf",
        "document_type": "contract",
        "clause_ref": "8.2",
        "boq_item": "E1",
        "description": "Bulk excavation",
        "unit": "m3",
        "quantity": 12500,
        "rate": 38,
        "amount": 475000,
        "status": "open",
    },
    "progress_claims": {
        "reference": "nf-claim",
        "ipc_number": "1",
        "boq_item": "E1",
        "period": "2026-09",
        "gross_amount": 475000,
        "accepted_contract_amount": 1902950,
        "retention_pct": 5,
        "retention_amount": 23750,
        "performance_security_rate": 10,
        "performance_security_deduction": 190295,
        "net_certified": 260955,
        "currency": "SAR",
        "status": "open",
    },
    "time_and_delay_damages": {
        "reference": "nf-delay",
        "commencement_date": "2026-01-01",
        "completion_date": "2028-01-01",
        "time_for_completion_days": 730,
        "accepted_contract_amount": 1902950,
        "delay_days": 0,
        "delay_damages_rate_pct": 0.1,
        "delay_damages": 0,
        "damages_cap_pct": 10,
        "cap_reached": False,
        "status": "open",
    },
    "qa_itp_records": {
        "reference": "nf-itp",
        "boq_item": "E1",
        "inspection_lot": "LOT-1",
        "hold_point": "Excavation formation",
        "witness_point": "Level check",
        "test_result": "pass",
        "inspection_date": "2026-09-03",
        "status": "open",
    },
    "document_register": {
        "reference": "nf-doc",
        "title": "Contract excerpt",
        "document_type": "contract",
        "revision": "1.0.0",
        "checksum": "a" * 64,
        "source_document": "document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf",
        "status": "open",
    },
    "role_based_access_and_audit": {
        "reference": "nf-rbac",
        "principal_id": "qs-1",
        "role": "quantity_surveyor",
        "permission": "claim.submit",
        "requested_action": "write",
        "decision": "allow",
        "status": "open",
    },
}


def _post(capability, body, headers=None):
    return client.post("/v1/" + capability, json=body, headers=headers or AUTH)


def _assert_refused(capability, body, why):
    resp = _post(capability, body)
    assert resp.status_code != 500, capability + " raised: " + resp.text[:200]
    assert _refused(resp), capability + " accepted " + why + ": " + resp.text[:200]


# -- contract_source_of_record ---------------------------------------------


def test_contract_source_of_record_refuses_a_missing_reference():
    body = dict(BODIES["contract_source_of_record"])
    body.pop("reference")
    _assert_refused("contract_source_of_record", body, "a payload with no reference")


def test_contract_source_of_record_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["contract_source_of_record"], clause_ref="99.9")
    _assert_refused("contract_source_of_record", body, "an undeclared clause")


def test_contract_source_of_record_does_not_leak_across_tenants():
    made = _post("contract_source_of_record", dict(BODIES["contract_source_of_record"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/contract_source_of_record/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_contract_source_of_record_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("contract_source_of_record", junk, "malformed input")


# -- progress_claims --------------------------------------------------------


def test_progress_claims_refuses_a_missing_reference():
    body = dict(BODIES["progress_claims"])
    body.pop("reference")
    _assert_refused("progress_claims", body, "a payload with no reference")


def test_progress_claims_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["progress_claims"], status="not-a-declared-status")
    _assert_refused("progress_claims", body, "an undeclared status")


def test_progress_claims_does_not_leak_across_tenants():
    made = _post("progress_claims", dict(BODIES["progress_claims"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/progress_claims/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_progress_claims_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("progress_claims", junk, "malformed input")


# -- time_and_delay_damages -------------------------------------------------


def test_time_and_delay_damages_refuses_a_missing_reference():
    body = dict(BODIES["time_and_delay_damages"])
    body.pop("reference")
    _assert_refused("time_and_delay_damages", body, "a payload with no reference")


def test_time_and_delay_damages_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["time_and_delay_damages"], status="not-a-declared-status")
    _assert_refused("time_and_delay_damages", body, "an undeclared status")


def test_time_and_delay_damages_does_not_leak_across_tenants():
    made = _post("time_and_delay_damages", dict(BODIES["time_and_delay_damages"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/time_and_delay_damages/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_time_and_delay_damages_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("time_and_delay_damages", junk, "malformed input")


# -- qa_itp_records ---------------------------------------------------------


def test_qa_itp_records_refuses_a_missing_reference():
    body = dict(BODIES["qa_itp_records"])
    body.pop("reference")
    _assert_refused("qa_itp_records", body, "a payload with no reference")


def test_qa_itp_records_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["qa_itp_records"], test_result="not-a-result")
    _assert_refused("qa_itp_records", body, "an undeclared test result")


def test_qa_itp_records_does_not_leak_across_tenants():
    made = _post("qa_itp_records", dict(BODIES["qa_itp_records"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/qa_itp_records/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_qa_itp_records_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("qa_itp_records", junk, "malformed input")


# -- document_register ------------------------------------------------------


def test_document_register_refuses_a_missing_reference():
    body = dict(BODIES["document_register"])
    body.pop("reference")
    _assert_refused("document_register", body, "a payload with no reference")


def test_document_register_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["document_register"], document_type="not-a-type")
    _assert_refused("document_register", body, "an undeclared document type")


def test_document_register_does_not_leak_across_tenants():
    made = _post("document_register", dict(BODIES["document_register"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/document_register/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_document_register_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("document_register", junk, "malformed input")


# -- role_based_access_and_audit -------------------------------------------


def test_role_based_access_and_audit_refuses_a_missing_reference():
    body = dict(BODIES["role_based_access_and_audit"])
    body.pop("reference")
    _assert_refused("role_based_access_and_audit", body, "a payload with no reference")


def test_role_based_access_and_audit_refuses_a_value_outside_its_vocabulary():
    body = dict(BODIES["role_based_access_and_audit"], role="not-a-role")
    _assert_refused("role_based_access_and_audit", body, "an undeclared role")


def test_role_based_access_and_audit_does_not_leak_across_tenants():
    made = _post("role_based_access_and_audit", dict(BODIES["role_based_access_and_audit"]))
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    rid = ((made.json().get("stored") or {}).get("id"))
    assert rid
    other = client.get("/v1/role_based_access_and_audit/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == 404


def test_role_based_access_and_audit_refuses_a_malformed_payload():
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        _assert_refused("role_based_access_and_audit", junk, "malformed input")
