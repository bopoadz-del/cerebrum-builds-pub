"""The platform modules behind the routes: authority, retrieval, answers, guards."""

from __future__ import annotations

import pytest

from app import authority, llm, retrieval, security, store

TENANT = "test-platform-modules"


def test_authority_ladder_puts_procedures_above_certified():
    resolved = authority.resolve(
        [
            authority.Claim(1, "certified value", "certified:kernel"),
            authority.Claim(4, "procedure value", "procedure:local"),
        ]
    )
    assert resolved["winner"] == "procedure value"
    assert resolved["authority"] == "4:procedures"
    labels = [item["label"] for item in resolved["divergences"]]
    assert labels == ["1:certified"]


def test_authority_labels_are_layer_number_and_name():
    assert authority.label(2) == "2:documents"
    with pytest.raises(ValueError):
        authority.label(9)


def test_retrieval_finds_a_registered_document_and_never_invents_one():
    store.save(
        "document_register",
        {
            "reference": "DOC-RET-1",
            "status": "open",
            "title": "Retention certificate register",
            "revision": "B",
            "document_type": "certificate",
            "source_filename": "retention.pdf",
            "checksum": "abc",
            "issued_date": "2026-09-03",
        },
        tenant_id=TENANT,
    )
    hits = retrieval.search("retention certificate", tenant_id=TENANT)
    assert hits and hits[0]["reference"] == "DOC-RET-1"
    assert retrieval.search("quantum chromodynamics", tenant_id=TENANT) == []


def test_retrieval_is_tenant_scoped():
    assert retrieval.search("retention certificate", tenant_id="some-other-tenant") == []


def test_answer_refuses_when_no_evidence_exists():
    out = llm.answer("quantum chromodynamics", tenant_id=TENANT)
    assert out["ok"] is False
    assert "no evidence" in out["error"]


def test_answer_cites_the_contract_clause_it_used():
    out = llm.answer("retention release at taking over", tenant_id=TENANT)
    assert out["ok"] is True
    assert out["authority"] == "2:documents"
    assert any(c["kind"] == "contract_clause" for c in out["citations"])


def test_bearer_parsing_and_constant_time_match():
    assert security.bearer_token("Bearer abc123") == "abc123"
    assert security.bearer_token("Basic abc123") is None
    assert security.bearer_token(None) is None
    assert security.tokens_match("abc", "abc") is True
    assert security.tokens_match("abc", "abd") is False


def test_private_address_guard_refuses_loopback_and_metadata():
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data",
                "http://localhost:8000/", "file:///etc/passwd"):
        with pytest.raises(security.SecurityError):
            security.assert_public_url(url)


def test_secret_redaction_keeps_only_the_tail():
    assert security.redact("supersecret", keep=4) == "*******cret"
    assert security.redact("abc", keep=4) == "***"


def test_persisting_capabilities_remember_the_record_they_are_given(monkeypatch):
    """The route persists what a handler accepts, for every capability that
    declares a persisted entity. The Store blocks are stubbed here so this
    test grades the route/handler/persistence wiring itself; the pilot suite
    grades the same path against the real vendored blocks."""
    import os

    from fastapi.testclient import TestClient

    from app import dispatch
    from app.main import app

    monkeypatch.setattr(dispatch, "execute", lambda *a, **k: {"status": "success", "result": {}})
    auth = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
    payloads = {
        "document_register": {
            "reference": "DOC-PERSIST-1", "status": "open", "title": "Contract excerpt",
            "revision": "A", "document_type": "contract",
            "source_filename": "contract.pdf", "checksum": "abc", "issued_date": "2026-09-03",
        },
        "claim_evidence_and_approvals": {
            "reference": "CLM-PERSIST-1", "status": "open", "claim_reference": "IPC-1",
            "evidence_ref": "EV-1", "preparer_id": "quantity-surveyor",
            "certifier_id": "contract-administrator", "decision": "approved",
            "claim_amount": 1000.0, "retention_amount": 50.0, "net_certified": 950.0,
        },
    }
    with TestClient(app) as client:
        for capability, payload in payloads.items():
            made = client.post("/v1/" + capability, json=payload, headers=auth)
            assert made.status_code == 200, made.text
            body = made.json()
            assert body.get("ok") is True, body
            record_id = body["id"]
            assert record_id is not None
            listed = client.get("/v1/" + capability, headers=auth).json()
            assert any(row["id"] == record_id for row in listed["items"])
            one = client.get(f"/v1/{capability}/{record_id}", headers=auth)
            assert one.status_code == 200
            assert one.json()["record"]["reference"] == payload["reference"]
