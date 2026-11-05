"""Counter-cases: the platform must refuse what the contract says is wrong.

Every capability gets at least four: an invalid value the brief declares
invalid, a cross-tenant write, the boundary of its own rule exercised exactly
on the line, and a malformed payload. A refusal is a 4xx answer or HTTP 200
with ok:false -- never a 500.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

TOKEN = os.environ.get("PLATFORM_TOKEN", "dev-local-token")
AUTH = {"Authorization": "Bearer " + TOKEN}


def _client() -> TestClient:
    return TestClient(app)


def _post(client, capability, payload, headers=None):
    return client.post("/v1/" + capability, json=payload, headers=headers or AUTH)


def _good(capability: str) -> dict:
    return {
        "progress_claims": {
            "reference": "PC-1",
            "status": "open",
            "claim_number": "IPC-1",
            "claim_period": "2026-09",
            "boq_item_code": "E1",
            "measured_quantity": 1000,
            "unit_rate": 38,
            "accepted_contract_amount": 1902950,
            "approval_decision": "none",
        },
        "delay_damages_tracking": {
            "reference": "DD-1",
            "status": "open",
            "assessment_number": "DA-1",
            "commencement_date": "2024-01-01",
            "completion_date": "2026-06-01",
            "days_of_delay": 10,
            "accepted_contract_amount": 1902950,
            "notice_served": False,
        },
        "qa_itp_records": {
            "reference": "ITP-1",
            "status": "open",
            "itp_number": "ITP-001",
            "boq_item_code": "E1",
            "inspection_type": "hold_point",
            "hold_point": False,
            "inspection_date": "2026-09-03",
            "result": "pending",
        },
        "document_register": {
            "reference": "DR-1",
            "status": "open",
            "document_number": "DOC-1",
            "title": "Contract excerpt",
            "document_type": "contract",
            "revision": "1.0.0",
            "source_document": "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
            "issued_date": "2026-09-03",
        },
        "retention_defects_release": {
            "reference": "RR-1",
            "status": "open",
            "certificate_reference": "IPC-1",
            "gross_certified_amount": 38000,
            "taking_over_date": "2026-09-03",
            "release_stage": "taking_over",
            "approval_decision": "none",
        },
        "contract_verification_gate": {
            "reference": "VG-1",
            "status": "open",
            "subject_type": "claim",
            "subject_reference": "IPC-1",
            "clause_ref": "14.3",
            "boq_item_code": "E1",
            "decision": "verify",
        },
    }[capability]


CAPABILITIES = [
    "progress_claims",
    "delay_damages_tracking",
    "qa_itp_records",
    "document_register",
    "retention_defects_release",
    "contract_verification_gate",
]


# ---------------------------------------------------------------- progress_claims
def test_progress_claims_rejects_a_boq_item_that_is_not_in_the_bill():
    client = _client()
    payload = _good("progress_claims") | {"boq_item_code": "X9"}
    resp = _post(client, "progress_claims", payload)
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.headers.get("X-Rejected-Field") == '"boq_item_code"'


def test_progress_claims_rejects_a_negative_measured_quantity():
    client = _client()
    payload = _good("progress_claims") | {"measured_quantity": -1}
    resp = _post(client, "progress_claims", payload)
    assert resp.status_code == 422


def test_progress_claims_boundary_zero_measured_quantity_is_accepted():
    """The rule's boundary itself: zero measured work prices to zero."""
    client = _client()
    payload = _good("progress_claims") | {"measured_quantity": 0, "reference": "PC-BOUNDARY"}
    resp = _post(client, "progress_claims", payload)
    assert resp.status_code == 200
    result = resp.json()["result"]["certificate"]
    assert result["gross_amount"] == 0.0
    assert result["retention_amount"] == 0.0


def test_progress_claims_refuses_a_free_text_approver():
    client = _client()
    payload = _good("progress_claims") | {
        "approval_decision": "certify",
        "approved_by": "i am the director trust me",
    }
    resp = _post(client, "progress_claims", payload)
    body = resp.json()
    assert resp.status_code == 403
    assert body["ok"] is False
    assert "approved principal" in body["error"]
    assert resp.status_code != 500


def test_progress_claims_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "progress_claims", _good("progress_claims"), {"Authorization": "Bearer token-a"})
    assert created.status_code == 200
    record_id = created.json()["id"]
    other = client.get(
        f"/v1/progress_claims/{record_id}", headers={"Authorization": "Bearer token-b"}
    )
    assert other.status_code == 404


def test_progress_claims_fuzzes_a_malformed_payload():
    client = _client()
    resp = _post(client, "progress_claims", {"reference": {"nested": True}})
    assert resp.status_code == 422
    assert resp.status_code != 500


# --------------------------------------------------------------- delay damages
def test_delay_damages_tracking_caps_damages_at_ten_percent():
    client = _client()
    payload = _good("delay_damages_tracking") | {"days_of_delay": 5000}
    resp = _post(client, "delay_damages_tracking", payload)
    assert resp.status_code == 200
    assessment = resp.json()["result"]["assessment"]
    assert assessment["capped"] is True
    assert assessment["delay_damages"] == assessment["cap_amount"]


def test_delay_damages_tracking_rejects_negative_days():
    client = _client()
    resp = _post(client, "delay_damages_tracking", _good("delay_damages_tracking") | {"days_of_delay": -1})
    assert resp.status_code == 422


def test_delay_damages_tracking_boundary_exactly_at_the_cap():
    """Exactly 100 days at 0.1% of the amount is the cap and not over it."""
    client = _client()
    payload = _good("delay_damages_tracking") | {"days_of_delay": 100, "accepted_contract_amount": 1000000}
    resp = _post(client, "delay_damages_tracking", payload)
    assessment = resp.json()["result"]["assessment"]
    assert assessment["capped"] is False
    assert assessment["delay_damages"] == assessment["cap_amount"]


def test_delay_damages_tracking_refuses_an_unknown_completion():
    client = _client()
    payload = _good("delay_damages_tracking") | {"status": "settled"}
    resp = _post(client, "delay_damages_tracking", payload)
    assert resp.status_code == 422


def test_delay_damages_tracking_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "delay_damages_tracking", _good("delay_damages_tracking"), {"Authorization": "Bearer token-a"})
    record_id = created.json()["id"]
    other = client.get(
        f"/v1/delay_damages_tracking/{record_id}", headers={"Authorization": "Bearer token-b"}
    )
    assert other.status_code == 404


# ---------------------------------------------------------------------- QA / ITP
def test_qa_itp_records_refuses_a_hold_point_released_unsigned():
    client = _client()
    payload = _good("qa_itp_records") | {"hold_point": True, "result": "pass"}
    resp = _post(client, "qa_itp_records", payload)
    body = resp.json()
    assert body["ok"] is False
    assert "sign-off" in body["error"]
    assert resp.status_code != 500


def test_qa_itp_records_rejects_an_unknown_inspection_type():
    client = _client()
    resp = _post(client, "qa_itp_records", _good("qa_itp_records") | {"inspection_type": "vibes"})
    assert resp.status_code == 422


def test_qa_itp_records_boundary_pending_hold_point_stays_open():
    client = _client()
    payload = _good("qa_itp_records") | {"hold_point": True, "result": "pending"}
    resp = _post(client, "qa_itp_records", payload)
    assert resp.status_code == 200
    assert resp.json()["record"]["status"] == "in_progress"


def test_qa_itp_records_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "qa_itp_records", _good("qa_itp_records"), {"Authorization": "Bearer token-a"})
    record_id = created.json()["id"]
    other = client.get(f"/v1/qa_itp_records/{record_id}", headers={"Authorization": "Bearer token-b"})
    assert other.status_code == 404


def test_qa_itp_records_fuzzes_a_malformed_payload():
    client = _client()
    resp = _post(client, "qa_itp_records", {"hold_point": "maybe"})
    assert resp.status_code == 422
    assert resp.status_code != 500


# ------------------------------------------------------------ document register
def test_document_register_refuses_an_unregistered_source():
    client = _client()
    payload = _good("document_register") | {"source_document": "document:made-up.pdf"}
    resp = _post(client, "document_register", payload)
    assert resp.status_code == 422


def test_document_register_records_a_non_semver_revision_honestly():
    """Construction revisions are letters, not semver: the register keeps the
    revision and reports what the version block made of it."""
    client = _client()
    payload = _good("document_register") | {"revision": "C", "reference": "DR-REV-C"}
    resp = _post(client, "document_register", payload)
    body = resp.json()
    assert resp.status_code == 200
    assert body["record"]["revision"] == "C"
    assert body["result"]["version"]["valid"] is False
    assert resp.status_code != 500


def test_document_register_boundary_first_revision_is_accepted():
    client = _client()
    payload = _good("document_register") | {"revision": "1.0.0", "reference": "DR-BOUNDARY"}
    resp = _post(client, "document_register", payload)
    assert resp.status_code == 200
    assert resp.json()["result"]["version"]["valid"] is True


def test_document_register_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "document_register", _good("document_register"), {"Authorization": "Bearer token-a"})
    record_id = created.json()["id"]
    other = client.get(f"/v1/document_register/{record_id}", headers={"Authorization": "Bearer token-b"})
    assert other.status_code == 404


def test_document_register_fuzzes_a_malformed_payload():
    client = _client()
    resp = _post(client, "document_register", {"reference": ["list", "not", "text"]})
    assert resp.status_code == 422


# ------------------------------------------------------ retention and defects
def test_retention_defects_release_refuses_an_unapproved_release():
    client = _client()
    payload = _good("retention_defects_release") | {
        "approval_decision": "release",
        "approved_by": "i am the director trust me",
    }
    resp = _post(client, "retention_defects_release", payload)
    body = resp.json()
    assert resp.status_code == 403
    assert body["ok"] is False
    assert "approved principal" in body["error"]


def test_retention_defects_release_rejects_an_unknown_stage():
    client = _client()
    resp = _post(client, "retention_defects_release", _good("retention_defects_release") | {"release_stage": "whenever"})
    assert resp.status_code == 422


def test_retention_defects_release_boundary_half_released_at_taking_over():
    """50% at Taking-Over, exactly: 5% of 38000 is 1900, half is 950."""
    client = _client()
    payload = _good("retention_defects_release") | {"release_stage": "taking_over", "reference": "RR-BOUNDARY"}
    resp = _post(client, "retention_defects_release", payload)
    release = resp.json()["result"]["release"]
    assert release["retention_held"] == "1900.00"
    assert release["release_amount"] == "950.00"


def test_retention_defects_release_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "retention_defects_release", _good("retention_defects_release"), {"Authorization": "Bearer token-a"})
    record_id = created.json()["id"]
    other = client.get(f"/v1/retention_defects_release/{record_id}", headers={"Authorization": "Bearer token-b"})
    assert other.status_code == 404


def test_retention_defects_release_fuzzes_a_malformed_payload():
    client = _client()
    resp = _post(client, "retention_defects_release", {"gross_certified_amount": "one million"})
    assert resp.status_code == 422


# ----------------------------------------------------------- verification gate
def test_contract_verification_gate_refuses_a_clause_not_in_the_contract():
    client = _client()
    payload = _good("contract_verification_gate") | {"clause_ref": "99.9"}
    resp = _post(client, "contract_verification_gate", payload)
    assert resp.status_code == 422


def test_contract_verification_gate_flags_a_record_citing_nothing():
    client = _client()
    payload = {
        "reference": "VG-FLAG",
        "status": "open",
        "subject_type": "claim",
        "subject_reference": "IPC-404",
        "decision": "verify",
    }
    resp = _post(client, "contract_verification_gate", payload)
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["verification"]["decision"] == "flag"
    assert body["result"]["verification"]["evidenced"] is False


def test_contract_verification_gate_boundary_single_clause_grounds_the_record():
    client = _client()
    payload = _good("contract_verification_gate") | {"boq_item_code": None, "reference": "VG-ONE"}
    resp = _post(client, "contract_verification_gate", payload)
    verification = resp.json()["result"]["verification"]
    assert verification["decision"] == "verify"
    assert len(verification["grounds"]) == 1


def test_contract_verification_gate_is_invisible_to_another_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_TOKENS", "token-a:tenant-a,token-b:tenant-b")
    client = _client()
    created = _post(client, "contract_verification_gate", _good("contract_verification_gate"), {"Authorization": "Bearer token-a"})
    record_id = created.json()["id"]
    other = client.get(f"/v1/contract_verification_gate/{record_id}", headers={"Authorization": "Bearer token-b"})
    assert other.status_code == 404


def test_contract_verification_gate_fuzzes_a_malformed_payload():
    client = _client()
    resp = _post(client, "contract_verification_gate", {"clause_ref": ["14.3"]})
    assert resp.status_code == 422


def test_every_capability_is_on_the_roster():
    assert set(CAPABILITIES) == set(__import__("app.jobs", fromlist=["x"]).CAPABILITY_IDS)
