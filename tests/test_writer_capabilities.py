"""Writer-owned acceptance tests for the six capabilities.

These exercise the live HTTP routes with the product's own model samples, the
declared placeholder refusal for the controlled register, and the four
counter-cases every capability refuses.
"""

from __future__ import annotations

import os

import pytest

from app.models import MODELS
from app.validation import sample_for_model

AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "")}

SAMPLE_CAPS = [
    "progress_claim_management",
    "delay_damages_tracking",
    "qa_itp_records",
    "contract_terms_governance",
    "commercial_dashboard",
]


def _sample(capability_id: str) -> dict:
    return sample_for_model(MODELS[capability_id])


@pytest.mark.parametrize("capability_id", SAMPLE_CAPS)
def test_capability_round_trip(client, capability_id):
    payload = _sample(capability_id)
    created = client.post("/v1/" + capability_id, json=payload, headers=AUTH)
    assert created.status_code == 200, created.text[:400]
    body = created.json()
    assert body["ok"] is True
    record_id = body["id"]
    assert record_id is not None
    assert body["record"]["id"] == record_id
    assert body["authority"]

    listed = client.get("/v1/" + capability_id, headers=AUTH)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["id"] == record_id for item in items)

    read = client.get("/v1/%s/%s" % (capability_id, record_id), headers=AUTH)
    assert read.status_code == 200
    assert read.json()["record"]["id"] == record_id


def test_document_register_answers_declared_unavailable_refusal(client):
    before = client.get("/v1/document_register", headers=AUTH)
    assert before.status_code == 200
    refused = client.post("/v1/document_register", json=_sample("document_register"), headers=AUTH)
    assert refused.status_code == 503
    body = refused.json()
    assert body["ok"] is False
    assert body["error_kind"] == "unavailable"
    assert body["settings"] == [
        "PROJECT_DOCUMENT_MANAGEMENT_SYSTEM_E_G_PROCORE_ACONEX_CREDENTIALS"
    ]
    after = client.get("/v1/document_register", headers=AUTH)
    assert after.json() == before.json()


def test_progress_claim_management_counter_cases(client):
    assert client.post("/v1/progress_claim_management", json={}).status_code == 401
    assert client.post("/v1/progress_claim_management", json={}, headers=AUTH).status_code == 422
    bad = _sample("progress_claim_management")
    bad["status"] = "__not_in_contract__"
    assert client.post("/v1/progress_claim_management", json=bad, headers=AUTH).status_code == 422
    assert client.get("/v1/progress_claim_management/999999", headers=AUTH).status_code == 404


def test_delay_damages_tracking_counter_cases(client):
    assert client.post("/v1/delay_damages_tracking", json={}).status_code == 401
    assert client.post("/v1/delay_damages_tracking", json={}, headers=AUTH).status_code == 422
    bad = _sample("delay_damages_tracking")
    bad["status"] = "__not_in_contract__"
    assert client.post("/v1/delay_damages_tracking", json=bad, headers=AUTH).status_code == 422
    assert client.get("/v1/delay_damages_tracking/999999", headers=AUTH).status_code == 404


def test_qa_itp_records_counter_cases(client):
    assert client.post("/v1/qa_itp_records", json={}).status_code == 401
    assert client.post("/v1/qa_itp_records", json={}, headers=AUTH).status_code == 422
    bad = _sample("qa_itp_records")
    bad["test_result"] = "__not_in_contract__"
    assert client.post("/v1/qa_itp_records", json=bad, headers=AUTH).status_code == 422
    assert client.get("/v1/qa_itp_records/999999", headers=AUTH).status_code == 404


def test_contract_terms_governance_counter_cases(client):
    assert client.post("/v1/contract_terms_governance", json={}).status_code == 401
    assert client.post("/v1/contract_terms_governance", json={}, headers=AUTH).status_code == 422
    bad = _sample("contract_terms_governance")
    bad["term_type"] = "__not_in_contract__"
    assert client.post("/v1/contract_terms_governance", json=bad, headers=AUTH).status_code == 422
    assert client.get("/v1/contract_terms_governance/999999", headers=AUTH).status_code == 404


def test_commercial_dashboard_counter_cases(client):
    assert client.post("/v1/commercial_dashboard", json={}).status_code == 401
    assert client.post("/v1/commercial_dashboard", json={}, headers=AUTH).status_code == 422
    bad = _sample("commercial_dashboard")
    bad["claim_status"] = "__not_in_contract__"
    assert client.post("/v1/commercial_dashboard", json=bad, headers=AUTH).status_code == 422
    assert client.get("/v1/commercial_dashboard/999999", headers=AUTH).status_code == 404


def test_document_register_counter_cases(client):
    assert client.post("/v1/document_register", json={}).status_code == 401
    # The catalogue entry is public; the records behind it are not.
    public = client.get("/v1/document_register")
    assert public.status_code == 200
    assert public.json()["items"] == []
    assert public.json()["authenticated"] is False
    assert client.delete("/v1/document_register/999999").status_code == 401
    assert client.get("/v1/document_register/999999", headers=AUTH).status_code == 404


def test_delay_damages_formula_uses_contract_terms():
    from app import contract_data, formulas

    result = formulas.delay_damages(
        accepted_contract_amount=1_000_000,
        daily_rate_pct=contract_data.DELAY_DAMAGES_DAILY_PCT,
        delay_days=10,
        cap_pct=contract_data.DELAY_DAMAGES_CAP_PCT,
    )
    assert result["uncapped"] == 10_000.0
    assert result["damages"] == 10_000.0
    assert formulas.IMPROVISED in result["authority"]


def test_document_intake_files_a_parsed_copy(client):
    text = b"Retention is five percent of each certificate.\nThe defects period runs from taking-over.\n"
    filed = client.post(
        "/v1/document_register/intake",
        files={"file": ("site-note.txt", text, "text/plain")},
        headers=AUTH,
    )
    assert filed.status_code == 200, filed.text[:400]
    body = filed.json()
    assert body["ok"] is True and body["parsed"] is True
    assert body["intake"]["characters"] > 0
    record_id = body["id"]
    listed = client.get("/v1/document_register", headers=AUTH)
    assert listed.status_code == 200
    assert any(item["id"] == record_id for item in listed.json()["items"])


def test_cited_answer_names_the_document_it_quoted(client):
    text = b"Measurement of earthworks is by compacted volume.\n"
    client.post(
        "/v1/document_register/intake",
        files={"file": ("measurement-note.txt", text, "text/plain")},
        headers=AUTH,
    )
    asked = client.post(
        "/v1/document_register/ask",
        json={"question": "How is measurement of earthworks taken?"},
        headers=AUTH,
    )
    assert asked.status_code == 200, asked.text[:400]
    body = asked.json()
    assert body["ok"] is True
    assert body["answer"].count("[1]") >= 1
    assert body["citations"][0]["document"].startswith("document:")
    assert body["authority"]


def test_ask_refuses_a_question_it_cannot_ground(client):
    empty = client.post("/v1/document_register/ask", json={}, headers=AUTH)
    assert empty.status_code == 422
    assert empty.json()["rejected_field"] == "question"
    unmatched = client.post(
        "/v1/document_register/ask",
        json={"question": "zzzzqqqq"},
        headers=AUTH,
    )
    assert unmatched.status_code == 200
    assert unmatched.json()["ok"] is False


def test_parse_requires_an_uploaded_file(client):
    assert client.post("/v1/document_register/parse", headers=AUTH).status_code == 422
    empty = client.post(
        "/v1/document_register/parse",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=AUTH,
    )
    assert empty.status_code == 422
    assert empty.json()["rejected_field"] == "file"


def test_intake_tracks_revisions_of_one_controlled_document(client):
    first = client.post(
        "/v1/document_register/intake",
        files={"file": ("itp-plan.txt", b"Hold point: proof of compaction.\n", "text/plain")},
        headers=AUTH,
    ).json()
    second = client.post(
        "/v1/document_register/intake",
        files={"file": ("itp-plan.txt", b"Hold point: proof of compaction and level survey.\n", "text/plain")},
        headers=AUTH,
    ).json()
    assert first["ok"] and second["ok"]
    assert first["record"]["reference"] == second["record"]["reference"]
    assert (first["record"]["revision"], second["record"]["revision"]) == ("A", "B")
    assert first["id"] != second["id"]
    repeat = client.post(
        "/v1/document_register/intake",
        files={"file": ("itp-plan.txt", b"Hold point: proof of compaction and level survey.\n", "text/plain")},
        headers=AUTH,
    ).json()
    assert repeat.get("unchanged") is True
    assert repeat["id"] == second["id"]
