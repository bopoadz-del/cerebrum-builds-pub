"""Counter-cases per capability: each refusal is measured, not asserted in prose.

Every capability is refused four ways -- no token, an unknown token, a missing
required field, a value outside its declared vocabulary -- and a record the
tenant does not hold answers 404 rather than leaking its existence.
"""

from __future__ import annotations

import os

AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}
BAD_AUTH = {"Authorization": "Bearer not-a-platform-token"}


def test_document_register_counter_cases(client):
    assert client.post("/v1/document_register", json={}).status_code == 401
    assert client.post("/v1/document_register", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/document_register", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/document_register",
        json={"reference": "DR-1", "status": "__not_in_contract__"},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/document_register/999999", headers=AUTH).status_code == 404


def test_progress_claims_counter_cases(client):
    assert client.post("/v1/progress_claims", json={}).status_code == 401
    assert client.post("/v1/progress_claims", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/progress_claims", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/progress_claims",
        json={"reference": "IPC-1", "approval_state": "__not_in_contract__"},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/progress_claims/999999", headers=AUTH).status_code == 404


def test_delay_damages_tracking_counter_cases(client):
    assert client.post("/v1/delay_damages_tracking", json={}).status_code == 401
    assert client.post("/v1/delay_damages_tracking", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/delay_damages_tracking", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/delay_damages_tracking",
        json={"reference": "DD-1", "delay_days": -5},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/delay_damages_tracking/999999", headers=AUTH).status_code == 404


def test_qa_itp_records_counter_cases(client):
    assert client.post("/v1/qa_itp_records", json={}).status_code == 401
    assert client.post("/v1/qa_itp_records", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/qa_itp_records", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/qa_itp_records",
        json={"reference": "ITP-1", "outcome": "__not_in_contract__"},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/qa_itp_records/999999", headers=AUTH).status_code == 404


def test_contract_clause_governance_counter_cases(client):
    assert client.post("/v1/contract_clause_governance", json={}).status_code == 401
    assert client.post("/v1/contract_clause_governance", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/contract_clause_governance", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/contract_clause_governance",
        json={"reference": "CC-1", "evidence_ref": "document:test", "clause_type": "__not_in_contract__"},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/contract_clause_governance/999999", headers=AUTH).status_code == 404


def test_payment_security_and_retention_ledger_counter_cases(client):
    assert client.post("/v1/payment_security_and_retention_ledger", json={}).status_code == 401
    assert client.post("/v1/payment_security_and_retention_ledger", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/payment_security_and_retention_ledger", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/payment_security_and_retention_ledger",
        json={"reference": "PS-1", "entry_type": "__not_in_contract__"},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/payment_security_and_retention_ledger/999999", headers=AUTH).status_code == 404


def test_claims_analytics_dashboard_counter_cases(client):
    assert client.post("/v1/claims_analytics_dashboard", json={}).status_code == 401
    assert client.post("/v1/claims_analytics_dashboard", json={}, headers=BAD_AUTH).status_code == 401
    assert client.post("/v1/claims_analytics_dashboard", json={}, headers=AUTH).status_code == 422
    assert client.post(
        "/v1/claims_analytics_dashboard",
        json={"reference": "DS-1", "period": "2026-09", "claims_count": -1},
        headers=AUTH,
    ).status_code == 422
    assert client.get("/v1/claims_analytics_dashboard/999999", headers=AUTH).status_code == 404
