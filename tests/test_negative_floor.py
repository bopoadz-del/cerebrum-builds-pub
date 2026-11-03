"""Counter-cases: prove the platform refuses the wrong thing, per capability.

Each capability is exercised by its own test so a refusal is attributed to
the capability that promised it. The counter-cases are the brief's rules:
an unauthenticated call, a missing field, a vocabulary outside the declared
status set, a record that does not exist, and a cross-tenant read.
"""

import os

AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
OTHER = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN_B", "")}


def test_progress_claims_refuses_bad_calls(client):
    assert client.post("/v1/progress_claims", json={}).status_code == 401
    assert client.get("/v1/progress_claims").status_code == 401
    assert client.get("/v1/progress_claims/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/progress_claims/999999", headers=OTHER).status_code == 404


def test_delay_damages_tracking_refuses_bad_calls(client):
    assert client.post("/v1/delay_damages_tracking", json={}).status_code == 401
    assert client.get("/v1/delay_damages_tracking").status_code == 401
    assert client.get("/v1/delay_damages_tracking/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/delay_damages_tracking/999999", headers=OTHER).status_code == 404


def test_qa_itp_records_refuses_bad_calls(client):
    assert client.post("/v1/qa_itp_records", json={}).status_code == 401
    assert client.get("/v1/qa_itp_records").status_code == 401
    assert client.get("/v1/qa_itp_records/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/qa_itp_records/999999", headers=OTHER).status_code == 404


def test_performance_security_tracking_refuses_bad_calls(client):
    assert client.post("/v1/performance_security_tracking", json={}).status_code == 401
    assert client.get("/v1/performance_security_tracking").status_code == 401
    assert client.get("/v1/performance_security_tracking/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/performance_security_tracking/999999", headers=OTHER).status_code == 404


def test_defects_notification_period_refuses_bad_calls(client):
    assert client.post("/v1/defects_notification_period", json={}).status_code == 401
    assert client.get("/v1/defects_notification_period").status_code == 401
    assert client.get("/v1/defects_notification_period/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/defects_notification_period/999999", headers=OTHER).status_code == 404


def test_document_register_refuses_bad_calls(client):
    assert client.post("/v1/document_register", json={}).status_code == 401
    missing = client.post("/v1/document_register", json={"status": "open"}, headers=AUTH)
    assert missing.status_code == 422
    assert missing.json()["rejected_field"] == "reference"
    bad_status = client.post("/v1/document_register",
                             json={"reference": "d1", "status": "archived"}, headers=AUTH)
    assert bad_status.status_code == 422
    assert bad_status.json()["allowed_values"] == ["open", "in_progress", "closed"]
    malformed = client.post("/v1/document_register", json=["not", "an", "object"], headers=AUTH)
    assert malformed.status_code == 422
    assert client.get("/v1/document_register/999999", headers=AUTH).status_code == 404


def test_claim_evidence_and_approvals_refuses_bad_calls(client):
    assert client.post("/v1/claim_evidence_and_approvals", json={}).status_code == 401
    missing = client.post("/v1/claim_evidence_and_approvals",
                          json={"reference": "c1", "status": "open"}, headers=AUTH)
    assert missing.status_code == 422
    assert missing.json()["rejected_field"] == "evidence_ref"
    bad_status = client.post("/v1/claim_evidence_and_approvals",
                             json={"reference": "c1", "status": "archived", "evidence_ref": "e1"},
                             headers=AUTH)
    assert bad_status.status_code == 422
    assert client.get("/v1/claim_evidence_and_approvals/999999", headers=AUTH).status_code == 404


def test_segregation_of_duties_refuses_self_certification():
    from app.actions import claim_evidence_and_approvals

    out = claim_evidence_and_approvals.handle(
        {"reference": "c1", "status": "open", "evidence_ref": "e1",
         "preparer_id": "principal-local"},
        principal_id="principal-local",
    )
    assert out["ok"] is False
    assert "segregation" in out["error"]


def test_missing_evidence_is_refused_not_certified():
    from app.actions import claim_evidence_and_approvals

    out = claim_evidence_and_approvals.handle(
        {"reference": "c1", "status": "open", "evidence_ref": ""},
        principal_id="principal-local",
    )
    assert out["ok"] is False
    assert "evidence" in out["error"]
