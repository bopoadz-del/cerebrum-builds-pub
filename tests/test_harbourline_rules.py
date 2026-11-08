"""Domain counter-cases for the Harbourline contracts platform.

Every capability is shown to refuse what the brief declares invalid, to be
tenant-isolated, and to refuse a malformed payload; the contract boundaries
(Clause 8.7 cap, Clause 14.3 retention, Clause 4.2 security) are exercised
exactly on the line.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import contract_terms, formulas, models, retrieval, store
from app.main import app

AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "")}
TENANT = "test-tenant"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _second_tenant():
    header = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN_B", "")}
    return header


def _valid(capability_id):
    cls = models.MODELS[capability_id]
    payload = {}
    for name in cls.FIELDS:
        rules = cls.CONSTRAINTS.get(name) or {}
        if not rules.get("required"):
            continue
        allowed = rules.get("allowed_values")
        payload[name] = allowed[0] if allowed else "counter-case"
    return payload


def test_progress_claim_processing_counter_cases(client):
    path = "/v1/progress_claim_processing"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("progress_claim_processing")
    bad["status"] = "certified"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("progress_claim_processing")).status_code == 401
    created = client.post(path, json=_valid("progress_claim_processing"), headers=AUTH)
    assert created.status_code == 200
    record_id = created.json()["id"]
    stolen = client.get("%s/%d" % (path, record_id), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"action": "create"}, headers=AUTH).status_code == 422


def test_delay_damages_tracking_counter_cases(client):
    path = "/v1/delay_damages_tracking"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("delay_damages_tracking")
    bad["status"] = "suspended"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("delay_damages_tracking")).status_code == 401
    created = client.post(path, json=_valid("delay_damages_tracking"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "delay_days": -5}, headers=AUTH).status_code == 422


def test_qa_itp_records_counter_cases(client):
    path = "/v1/qa_itp_records"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("qa_itp_records")
    bad["status"] = "signed"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("qa_itp_records")).status_code == 401
    created = client.post(path, json=_valid("qa_itp_records"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "hold_point": "yes"}, headers=AUTH).status_code == 422


def test_document_register_counter_cases(client):
    path = "/v1/document_register"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("document_register")
    bad["status"] = "archived"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("document_register")).status_code == 401
    created = client.post(path, json=_valid("document_register"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "issued_date": "not-a-date"}, headers=AUTH).status_code == 422


def test_contract_clause_grounding_counter_cases(client):
    path = "/v1/contract_clause_grounding"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("contract_clause_grounding")
    bad["status"] = "answered"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("contract_clause_grounding")).status_code == 401
    created = client.post(path, json=_valid("contract_clause_grounding"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "evidence_count": -1}, headers=AUTH).status_code == 422


def test_performance_security_tracking_counter_cases(client):
    path = "/v1/performance_security_tracking"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("performance_security_tracking")
    bad["status"] = "expired"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("performance_security_tracking")).status_code == 401
    created = client.post(path, json=_valid("performance_security_tracking"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "required_amount": -1}, headers=AUTH).status_code == 422


def test_compliance_dashboard_counter_cases(client):
    path = "/v1/compliance_dashboard"
    assert client.post(path, json={}, headers=AUTH).status_code == 422
    bad = _valid("compliance_dashboard")
    bad["status"] = "live"
    assert client.post(path, json=bad, headers=AUTH).status_code == 422
    assert client.post(path, json=_valid("compliance_dashboard")).status_code == 401
    created = client.post(path, json=_valid("compliance_dashboard"), headers=AUTH)
    assert created.status_code == 200
    stolen = client.get("%s/%d" % (path, created.json()["id"]), headers=_second_tenant())
    assert stolen.status_code == 404
    assert client.post(path, json={"reference": "x", "status": "open", "claims_open": -2}, headers=AUTH).status_code == 422


def test_unknown_capability_is_404(client):
    assert client.get("/v1/not_a_capability", headers=AUTH).status_code == 404


def test_delay_damages_boundary_at_the_clause_8_7_cap():
    amount = contract_terms.ACCEPTED_CONTRACT_AMOUNT
    at_line = formulas.delay_damages(amount, 100)
    assert at_line["cap"] == pytest.approx(amount * 0.10)
    assert at_line["value"] == pytest.approx(at_line["cap"])
    assert at_line["capped"] is False
    beyond = formulas.delay_damages(amount, 101)
    assert beyond["capped"] is True
    assert beyond["value"] == pytest.approx(beyond["cap"])
    assert beyond["uncapped_value"] > beyond["cap"]


def test_retention_and_security_are_the_contract_percentages():
    retention = formulas.retention(1_000_000)
    assert retention["value"] == pytest.approx(50_000)
    assert contract_terms.RETENTION_RATIO == pytest.approx(0.05)
    security = formulas.performance_security_requirement(1_000_000)
    assert security["value"] == pytest.approx(100_000)
    assert contract_terms.PERFORMANCE_SECURITY_RATIO == pytest.approx(0.10)


def test_retrieval_round_trip_and_negative_control(client):
    marker = "grounding-marker clause 8.7 delay damages cap"
    ingested = client.post("/v1/rag/ingest", json={"text": marker}, headers=AUTH)
    assert ingested.status_code == 200
    hit = client.post("/v1/rag/query", json={"q": "delay damages cap clause 8.7"}, headers=AUTH)
    body = hit.json()
    assert hit.status_code == 200 and body["count"] >= 1
    miss = client.post("/v1/rag/query", json={"q": "zzzz-never-planted-term"}, headers=AUTH)
    assert miss.json()["count"] == 0


def test_grounded_answer_carries_its_authority(client):
    answer = client.post(
        "/v1/contract_clause_grounding",
        json={"reference": "grounding-1", "status": "open", "question": "What is the delay damages rate?"},
        headers=AUTH,
    )
    payload = answer.json()
    assert answer.status_code == 200 and payload["ok"] is True
    result = payload["result"]
    assert "document:" in " ".join(result["citations"])
    assert result["authority"].startswith("documents")


def test_malformed_payload_is_fuzzed(client):
    fuzz = [["not", "an", "object"], "text", 42, None]
    for index, body in enumerate(fuzz):
        response = client.post(
            "/v1/progress_claim_processing",
            json=body if body is not None else {},
            headers=AUTH,
        )
        assert response.status_code in (401, 422), (index, response.status_code)


def test_store_is_tenant_scoped():
    saved = store.save("document_register", {"reference": "isolation"}, tenant_id=TENANT)
    assert store.get("document_register", saved["id"], tenant_id="other-tenant") is None
    assert store.get("document_register", saved["id"], tenant_id=TENANT) is not None


# --- The brief's rules, exercised through the capability routes ------------
# Each assertion is on the rule's effect in the handler's own result, so a
# handler that drops the clause rule (no cap, no retention, no coverage
# test, no hold point) cannot pass by returning a constant answer.


def _post(client, capability, payload):
    response = client.post("/v1/" + capability, json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True, body
    return body["result"]


def test_delay_damages_rule_effect_through_the_handler(client):
    base = {"reference": "delay-rule", "status": "open", "accepted_contract_amount": 100_000}

    below = _post(client, "delay_damages_tracking", {**base, "delay_days": 50})
    assert below["delay_damages_amount"] == pytest.approx(5_000)
    assert below["cap_applied"] is False

    at_cap = _post(client, "delay_damages_tracking", {**base, "delay_days": 100})
    assert at_cap["delay_damages_cap"] == pytest.approx(10_000)
    assert at_cap["delay_damages_amount"] == pytest.approx(10_000)
    assert at_cap["cap_applied"] is False

    beyond = _post(client, "delay_damages_tracking", {**base, "delay_days": 101})
    assert beyond["delay_damages_amount"] == pytest.approx(10_000)
    assert beyond["delay_damages_uncapped"] == pytest.approx(10_100)
    assert beyond["cap_applied"] is True


def test_delay_damages_extension_reduces_net_delay(client):
    result = _post(
        client,
        "delay_damages_tracking",
        {
            "reference": "delay-extension",
            "status": "open",
            "accepted_contract_amount": 100_000,
            "delay_days": 30,
            "extension_days": 10,
        },
    )
    assert result["net_delay_days"] == pytest.approx(20)
    assert result["delay_damages_amount"] == pytest.approx(2_000)


def test_progress_claim_retention_rule_effect(client):
    result = _post(
        client,
        "progress_claim_processing",
        {"reference": "claim-rule", "status": "open", "certified_amount": 100_000},
    )
    assert result["certified_amount"] == pytest.approx(100_000)
    assert result["retention_rate"] == pytest.approx(0.05)
    assert result["retention_amount"] == pytest.approx(5_000)
    assert result["net_payable"] == pytest.approx(95_000)


def test_progress_claim_measured_quantity_times_rate(client):
    result = _post(
        client,
        "progress_claim_processing",
        {
            "reference": "claim-measured",
            "status": "open",
            "boq_item": "E1",
            "measured_quantity": 10,
            "boq_rate": 38,
        },
    )
    assert result["certified_amount"] == pytest.approx(380)
    assert result["retention_amount"] == pytest.approx(19)
    assert result["net_payable"] == pytest.approx(361)


def test_performance_security_cover_and_expiry_rules(client):
    short = _post(
        client,
        "performance_security_tracking",
        {
            "reference": "security-short",
            "status": "open",
            "accepted_contract_amount": 100_000,
            "secured_amount": 5_000,
        },
    )
    assert short["required_amount"] == pytest.approx(10_000)
    assert short["coverage_ratio"] == pytest.approx(0.5)
    assert short["below_required_cover"] is True

    full = _post(
        client,
        "performance_security_tracking",
        {
            "reference": "security-full",
            "status": "open",
            "accepted_contract_amount": 100_000,
            "secured_amount": 10_000,
            "expiry_date": "2099-01-01",
        },
    )
    assert full["coverage_ratio"] == pytest.approx(1.0)
    assert full["below_required_cover"] is False
    assert full["renewal_due"] is False


def test_qa_itp_hold_point_and_result_rule(client):
    def _itp(reference, **extra):
        payload = {"reference": reference, "status": "open", "itp_number": reference}
        payload.update(extra)
        return _post(client, "qa_itp_records", payload)

    assert _itp("itp-hold", hold_point=True, result="pass")["verdict"] == "hold"
    assert _itp("itp-pass", hold_point=False, result="pass")["verdict"] == "pass"
    assert _itp("itp-pending", hold_point=False)["verdict"] == "pending"


def test_document_register_hash_tracks_content(client):
    first = _post(
        client,
        "document_register",
        {
            "reference": "doc-a",
            "status": "open",
            "document_title": "Contract excerpt",
            "document_revision": "A",
            "linked_clause": contract_terms.RETENTION,
        },
    )
    second = _post(
        client,
        "document_register",
        {
            "reference": "doc-b",
            "status": "open",
            "document_title": "Contract excerpt",
            "document_revision": "B",
            "linked_clause": contract_terms.RETENTION,
        },
    )
    assert first["sha256"] and second["sha256"]
    assert first["sha256"] != second["sha256"]
    assert "document:" in " ".join(first["citations"])


def test_grounding_answers_with_evidence_and_refuses_without(client):
    answered = _post(
        client,
        "contract_clause_grounding",
        {
            "reference": "ground-rule",
            "status": "open",
            "question": "delay damages rate and cap clause 8.7",
        },
    )
    assert answered["answered"] is True
    assert answered["evidence_count"] >= 1
    assert contract_terms.DELAY_DAMAGES in answered["clause_reference"] or contract_terms.DELAY_DAMAGES in " ".join(answered["citations"])

    refused = _post(
        client,
        "contract_clause_grounding",
        {
            "reference": "ground-refuse",
            "status": "open",
            "question": "zzzz never mentioned quantum chromodynamics",
        },
    )
    assert refused["answered"] is False
    assert refused["evidence_count"] == 0


def test_dashboard_view_varies_with_the_record_it_is_given(client):
    first = _post(
        client,
        "compliance_dashboard",
        {"reference": "dash-a", "status": "open", "period": "2026-10", "claims_open": 2},
    )
    second = _post(
        client,
        "compliance_dashboard",
        {"reference": "dash-b", "status": "open", "period": "2026-11", "claims_open": 7},
    )
    assert first["declared"] != second["declared"]
    assert first["period"] != second["period"]
    assert first != second


def test_progress_claim_retention_releases_in_two_stages(client):
    result = _post(
        client,
        "progress_claim_processing",
        {
            "reference": "claim-release",
            "status": "open",
            "certified_amount": 100_000,
            "taking_over_date": "2026-06-30",
        },
    )
    assert result["retention_release_at_taking_over"] == pytest.approx(2_500)
    assert result["retention_release_at_defects_end"] == pytest.approx(2_500)
    assert result["taking_over_date"] == "2026-06-30"
    assert result["defects_end_date"] == "2027-06-30"


def test_grounding_refuses_without_evidence(client):
    result = _post(
        client,
        "contract_clause_grounding",
        {"reference": "grounding-negative", "status": "open", "question": "zqxwv unrelated token"},
    )
    assert result["evidence_sufficient"] is False
    assert result["refused_for_insufficient_evidence"] is True
    assert result["answered"] is False


def test_document_register_version_chain_and_clause_link(client):
    result = _post(
        client,
        "document_register",
        {
            "reference": "revision-b",
            "status": "open",
            "document_title": "Interim Payment Certificate",
            "document_revision": "B",
            "supersedes": "revision-a",
            "linked_clause": contract_terms.RETENTION,
        },
    )
    assert result["linked_clause_valid"] is True
    assert result["version_chain"][0]["revision"] == "B"
    assert result["version_chain"][0]["supersedes"] == "revision-a"


def test_performance_security_missing_cover_is_below_required(client):
    result = _post(
        client,
        "performance_security_tracking",
        {"reference": "security-missing", "status": "open", "accepted_contract_amount": 100_000},
    )
    assert result["secured_amount"] == pytest.approx(0)
    assert result["coverage_ratio"] == pytest.approx(0)
    assert result["below_required_cover"] is True
