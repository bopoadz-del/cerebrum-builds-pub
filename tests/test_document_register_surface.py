"""The document register's intake, search and cited-answer surface.

The register is not only a table of metadata: an uploaded document is parsed
into the text its entry stands for, that text is findable through the register
search, and a question is answered with the passage and the citation of the
document the tenant attached.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}

NOTE = b"Retention is five percent of each interim payment certificate. Half is released at taking-over."


def _upload(name="site-note.txt", body=NOTE):
    return client.post(
        "/v1/document_register/intake",
        headers=AUTH,
        files={"file": (name, body, "text/plain")},
    )


def test_an_uploaded_document_is_registered_parsed_and_searchable():
    response = _upload()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["parsed"] is True
    assert body["intake"]["characters"] > 0
    assert body["id"] is not None
    record = body["record"]
    assert record["source_document"].startswith("document:")
    assert record["checksum"]

    found = client.get("/v1/document_register/search?q=retention", headers=AUTH)
    assert found.status_code == 200, found.text
    ids = [item["id"] for item in found.json()["items"]]
    assert body["id"] in ids


def test_a_question_is_answered_from_the_registered_text_with_a_citation():
    registered = _upload("retention-note.txt")
    assert registered.status_code == 200, registered.text
    asked = client.post(
        "/v1/document_register/ask",
        headers=AUTH,
        json={"question": "What does the note say about retention?"},
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["ok"] is True
    assert body["citations"]
    assert body["citations"][0]["document"].startswith("document:")
    assert "[1]" in body["answer"]
    assert body["authority"]


def test_intake_requires_the_bearer_token():
    response = client.post(
        "/v1/document_register/intake",
        files={"file": ("site-note.txt", NOTE, "text/plain")},
    )
    assert response.status_code == 401


def test_ask_without_a_question_is_refused_with_the_field_named():
    response = client.post("/v1/document_register/ask", headers=AUTH, json={})
    assert response.status_code == 422
    assert response.json()["rejected_field"] == "question"
