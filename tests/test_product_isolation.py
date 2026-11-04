"""Tenant isolation: a record one tenant stored is invisible to another.

The tenant comes from the bearer token, never the payload; a cross-tenant read
answers 404 (not 403) so existence never leaks, and a cross-tenant write
answers 404 rather than silently updating someone else's row.
"""

from __future__ import annotations

from tests import product_testkit as kit

CAPABILITY = "track_management"


def _store_one(client, monkeypatch, reference: str = "iso-1") -> int:
    kit.stub_blocks(monkeypatch)
    body = kit.payload(CAPABILITY)
    body["reference"] = reference
    created = client.post(
        "/v1/" + CAPABILITY, json=body, headers=kit.auth("dev-local-token")
    )
    assert created.status_code == 200, created.text[:300]
    return int(created.json()["id"])


def test_another_tenant_cannot_read_the_record(client, monkeypatch):
    record_id = _store_one(client, monkeypatch)
    resp = client.get("/v1/%s/%s" % (CAPABILITY, record_id), headers=kit.auth("dev-local-token-b"))
    assert resp.status_code == 404


def test_another_tenant_does_not_see_it_in_the_list(client, monkeypatch):
    _store_one(client, monkeypatch, "iso-2")
    listed = client.get("/v1/" + CAPABILITY, headers=kit.auth("dev-local-token-b"))
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_another_tenant_cannot_update_or_delete_it(client, monkeypatch):
    record_id = _store_one(client, monkeypatch, "iso-3")
    others = kit.auth("dev-local-token-b")
    assert client.put("/v1/%s/%s" % (CAPABILITY, record_id), json={"title": "x"}, headers=others).status_code == 404
    assert client.delete("/v1/%s/%s" % (CAPABILITY, record_id), headers=others).status_code == 404


def test_reading_without_a_token_is_401_everywhere(client):
    for path in ("/v1/track_management", "/v1/track_management/1", "/v1/capabilities", "/v1/rag/documents"):
        assert client.get(path).status_code == 401, path
    assert client.post("/v1/track_management", json={}).status_code == 401
    assert client.post("/v1/rag/ingest", json={"text": "x"}).status_code == 401
