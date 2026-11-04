"""The product's own round-trip and surface suite.

Each capability that is servable today is given a record and must hand it back;
the two declared-placeholder capabilities must answer their typed refusal and
store nothing. The block boundary is stubbed here so the test measures the
product's path, not a vendored block's internal contract (the factory's pilot
suite runs the real blocks).
"""

from __future__ import annotations

import uuid

import pytest

from app import placeholders
from app.models import MODELS
from tests import product_testkit as kit

SERVABLE = [cap for cap in MODELS if not placeholders.missing_connectors(cap)]
PLACEHOLDER = [cap for cap in MODELS if placeholders.missing_connectors(cap)]


def test_console_is_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    body = resp.text
    # A page that lists routes it never calls is a facade: the console reads
    # the roster from the API and posts to the capability route.
    assert "/v1/capabilities" in body
    assert "/v1/" in body


@pytest.mark.parametrize("capability", SERVABLE)
def test_capability_remembers_the_record_it_was_given(client, monkeypatch, capability):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    body = kit.payload(capability)
    body["reference"] = "rt-" + uuid.uuid4().hex[:8]

    created = client.post("/v1/" + capability, json=body, headers=headers)
    assert created.status_code == 200, created.text[:400]
    answer = created.json()
    assert answer["ok"] is True
    assert answer["stored"]["id"] == answer["id"]
    assert answer["result"]["reference"] == body["reference"]
    assert answer["authority"].startswith("layer ")

    listed = client.get("/v1/" + capability, headers=headers)
    assert listed.status_code == 200
    rows = listed.json()["items"]
    assert any(row["reference"] == body["reference"] for row in rows)

    fetched = client.get("/v1/%s/%s" % (capability, answer["id"]), headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["record"]["reference"] == body["reference"]


@pytest.mark.parametrize("capability", PLACEHOLDER)
def test_placeholder_capability_refuses_and_stores_nothing(client, capability):
    headers = kit.auth()
    before = client.get("/v1/" + capability, headers=headers).json()
    resp = client.post("/v1/" + capability, json=kit.payload(capability), headers=headers)
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert body["error_kind"] == "unavailable"
    assert body["settings"] == ["EMAIL_DELIVERY_CREDENTIALS"]
    after = client.get("/v1/" + capability, headers=headers).json()
    assert after == before


def test_retrieval_round_trip_finds_ingested_text_and_not_an_absent_nonce(client):
    headers = kit.auth()
    nonce = uuid.uuid4().hex[:10]
    absent = uuid.uuid4().hex[:10]
    text = "PRODUCT-PLANT-%s the reorder threshold procedure" % nonce

    planted = client.post("/v1/rag/ingest", json={"text": text, "title": "procedure"}, headers=headers)
    assert planted.status_code == 200, planted.text[:300]

    hit = client.post("/v1/rag/query", json={"q": "PRODUCT-PLANT-%s" % nonce}, headers=headers)
    assert hit.status_code == 200
    payload = hit.json()
    assert any(nonce in row["text"] for row in payload["hits"])
    assert payload["authority"]

    miss = client.get("/v1/rag/query", params={"q": absent}, headers=headers)
    assert miss.status_code == 200
    assert miss.json()["hits"] == []
