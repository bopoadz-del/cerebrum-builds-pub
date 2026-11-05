"""Retrieval: what you ingest is findable, and a term you never ingested is not."""

from __future__ import annotations

import uuid


def test_an_ingested_document_is_findable_again(client, auth):
    nonce = uuid.uuid4().hex[:12]
    marker = "PROVENANCE-%s the constraint scheduling procedure" % nonce
    ingested = client.post(
        "/v1/rag/ingest",
        json={"text": marker, "source": "board-note-%s.txt" % nonce},
        headers=auth,
    )
    assert ingested.status_code == 200
    assert ingested.json()["ok"] is True

    found = client.post("/v1/rag/query", json={"q": marker}, headers=auth)
    assert found.status_code == 200
    body = found.json()
    assert body["ok"] is True
    assert body["results"], "the ingested document was not retrievable"
    assert nonce in body["results"][0]["content"]
    assert body["authority"]["layer"] == 2


def test_a_query_for_a_term_never_ingested_returns_nothing(client, auth):
    absent = "ABSENT-" + uuid.uuid4().hex[:12]
    resp = client.get("/v1/rag/query", params={"q": absent}, headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert absent not in str(body.get("results"))


def test_ingest_without_text_is_refused(client, auth):
    resp = client.post("/v1/rag/ingest", json={"source": "empty.txt"}, headers=auth)
    assert resp.status_code == 422
    assert resp.json()["rejected_field"] == "text"


def test_query_without_a_term_is_refused(client, auth):
    resp = client.get("/v1/rag/query", headers=auth)
    assert resp.status_code == 422


def test_the_corpus_is_tenant_scoped(client, auth, auth_b):
    nonce = uuid.uuid4().hex[:12]
    marker = "TENANT-SCOPED-%s only one tenant may see this" % nonce
    assert client.post("/v1/rag/ingest", json={"text": marker}, headers=auth).status_code == 200
    other = client.post("/v1/rag/query", json={"q": marker}, headers=auth_b)
    assert other.status_code == 200
    assert other.json()["results"] == []
