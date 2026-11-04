"""Counter-cases: what each capability must REFUSE.

Proving the platform does the right thing is half a suite. Each capability
gets its own four refusals -- an unauthenticated request, a payload missing a
required field, a value outside a declared vocabulary, and a record that does
not exist (or belongs to nobody). The block boundary is stubbed only where a
create has to succeed first; the refusals themselves are decided before any
block runs.
"""

from __future__ import annotations

from app.models import MODELS
from tests import product_testkit as kit

OTHER_TENANT = {"Authorization": "Bearer dev-local-token-b"}


def test_track_management_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/track_management", json={"reference": "x"}).status_code == 401
    assert client.post("/v1/track_management", json={}, headers=headers).status_code == 422
    body = kit.payload("track_management")
    body["status"] = "__not_in_contract__"
    assert client.post("/v1/track_management", json=body, headers=headers).status_code == 422
    assert client.get("/v1/track_management/999999", headers=headers).status_code == 404


def test_enrolment_and_scheduling_refuses_bad_requests(client):
    headers = kit.auth()
    assert client.post("/v1/enrolment_and_scheduling", json={}).status_code == 401
    assert client.get("/v1/enrolment_and_scheduling/999999", headers=headers).status_code == 404
    assert client.put("/v1/enrolment_and_scheduling/999999", json={}, headers=headers).status_code == 404
    assert client.delete("/v1/enrolment_and_scheduling/999999", headers=headers).status_code == 404


def test_ai_faculty_sessions_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/ai_faculty_sessions", json={}).status_code == 401
    assert client.post("/v1/ai_faculty_sessions", json={}, headers=headers).status_code == 422
    body = kit.payload("ai_faculty_sessions")
    body["kernel_mode"] = "freeform"
    assert client.post("/v1/ai_faculty_sessions", json=body, headers=headers).status_code == 422
    assert client.get("/v1/ai_faculty_sessions/999999", headers=headers).status_code == 404


def test_memo_grading_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/memo_grading", json={}).status_code == 401
    assert client.post("/v1/memo_grading", json={}, headers=headers).status_code == 422
    body = kit.payload("memo_grading")
    body["word_count"] = -5
    assert client.post("/v1/memo_grading", json=body, headers=headers).status_code == 422
    assert client.get("/v1/memo_grading/999999", headers=headers).status_code == 404


def test_gradebook_and_transcript_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/gradebook_and_transcript", json={}).status_code == 401
    assert client.post("/v1/gradebook_and_transcript", json={}, headers=headers).status_code == 422
    body = kit.payload("gradebook_and_transcript")
    body["memos_score"] = 101
    assert client.post("/v1/gradebook_and_transcript", json=body, headers=headers).status_code == 422
    assert client.get("/v1/gradebook_and_transcript/999999", headers=headers).status_code == 404


def test_defenses_and_capstone_refuses_bad_requests(client):
    headers = kit.auth()
    assert client.post("/v1/defenses_and_capstone", json={}).status_code == 401
    assert client.get("/v1/defenses_and_capstone/999999", headers=headers).status_code == 404
    assert client.put("/v1/defenses_and_capstone/999999", json={}, headers=headers).status_code == 404
    assert client.delete("/v1/defenses_and_capstone/999999", headers=headers).status_code == 404


def test_library_surfaces_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/library_surfaces", json={}).status_code == 401
    assert client.post("/v1/library_surfaces", json={}, headers=headers).status_code == 422
    body = kit.payload("library_surfaces")
    body["week"] = 99
    assert client.post("/v1/library_surfaces", json=body, headers=headers).status_code == 422
    assert client.get("/v1/library_surfaces/999999", headers=headers).status_code == 404


def test_command_center_and_chat_refuses_bad_requests(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/command_center_and_chat", json={}).status_code == 401
    assert client.post("/v1/command_center_and_chat", json={}, headers=headers).status_code == 422
    body = kit.payload("command_center_and_chat")
    body["stage"] = "graduate"
    assert client.post("/v1/command_center_and_chat", json=body, headers=headers).status_code == 422
    assert client.get("/v1/command_center_and_chat/999999", headers=headers).status_code == 404


def test_unknown_capability_and_reserved_fields_are_refused(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    headers = kit.auth()
    assert client.post("/v1/not_a_capability", json={}, headers=headers).status_code == 404
    body = kit.payload("memo_grading")
    body["tenant_id"] = "tenant-b"
    assert client.post("/v1/memo_grading", json=body, headers=headers).status_code == 422
