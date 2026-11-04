"""The currency a money path uses, and the verb each retrieval route takes.

The platform refuses to invent a currency: it reads the deploy setting, then
the declared locale (both through ``app.money_settings``), then the currency
the contract's own documents price in. A deployment with none of the three
still refuses -- it never guesses SAR, USD or anything else.
"""

from __future__ import annotations

import json
import os

from app import block_inputs

AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}


def test_deploy_setting_wins_over_the_contract_record(monkeypatch):
    monkeypatch.setenv("PLATFORM_CURRENCY", "AED")
    assert block_inputs.configured_currency() == "AED"


def test_contract_record_supplies_the_currency_the_documents_price_in(monkeypatch, tmp_path):
    monkeypatch.delenv("PLATFORM_CURRENCY", raising=False)
    record = tmp_path / "source_of_record.json"
    record.write_text(json.dumps({"currency": "SAR"}), encoding="utf-8")
    monkeypatch.setattr(block_inputs, "SOURCE_OF_RECORD", record)
    # A missing declared locale plus no deploy setting leaves the contract's
    # own declaration as the only source; it is data, not a code constant.
    monkeypatch.setattr("app.money_settings._declared", lambda: {})
    assert block_inputs.configured_currency() == "SAR"


def test_no_declaration_anywhere_declines_to_invent_one(monkeypatch, tmp_path):
    monkeypatch.delenv("PLATFORM_CURRENCY", raising=False)
    monkeypatch.setattr(block_inputs, "SOURCE_OF_RECORD", tmp_path / "absent.json")
    monkeypatch.setattr("app.money_settings._declared", lambda: {})
    assert block_inputs.configured_currency() == ""


def test_malformed_contract_currency_is_not_used(monkeypatch, tmp_path):
    monkeypatch.delenv("PLATFORM_CURRENCY", raising=False)
    record = tmp_path / "source_of_record.json"
    record.write_text(json.dumps({"currency": "not-a-code"}), encoding="utf-8")
    monkeypatch.setattr(block_inputs, "SOURCE_OF_RECORD", record)
    monkeypatch.setattr("app.money_settings._declared", lambda: {})
    assert block_inputs.configured_currency() == ""


def test_ingest_takes_post_and_says_so_for_get(client):
    assert client.get("/v1/rag/ingest").status_code == 401
    response = client.get("/v1/rag/ingest", headers=AUTH)
    assert response.status_code == 405
    assert "POST" in response.headers.get("allow", "")


def test_retrieval_query_answers_or_refuses_with_an_authority_label(client):
    client.post(
        "/v1/rag/ingest",
        json={"text": "Clause 14.3 Retention: 5% of each Interim Payment Certificate.", "source": "contract"},
        headers=AUTH,
    )
    hit = client.get("/v1/rag/query", params={"q": "retention certificate"}, headers=AUTH)
    assert hit.status_code == 200
    body = hit.json()
    assert body["ok"] is True and body["authority"]
