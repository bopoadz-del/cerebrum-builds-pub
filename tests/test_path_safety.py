"""Caller text never becomes a path outside the persistence root."""

from __future__ import annotations

import os
from pathlib import Path

from app.block_inputs import prepare_block_input, safe_stem


def test_safe_stem_reduces_traversal_to_a_plain_name():
    assert "/" not in safe_stem("../../etc/passwd")
    assert ".." not in safe_stem("../../etc/passwd").replace("..-", "-")
    assert safe_stem("") == "record"
    assert safe_stem("IPC/001 .. x") == "IPC-001-x"


def test_prepared_inputs_stay_under_the_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    record = {
        "reference": "../../escape/IPC-1",
        "document_type": "drawing",
        "revision": "B",
        "status": "open",
    }
    for block in ("storage", "pdf"):
        payload = prepare_block_input("document_register", block, record, "tenant-a")
        path = Path(str(payload.get("file_path") or ""))
        assert path.is_file(), (block, path)
        assert str(path.resolve()).startswith(str(tmp_path.resolve())), (block, path)
    assert not (tmp_path.parent / "escape").exists()


def test_reference_with_a_traversal_still_persists(client, tmp_path):
    headers = {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "dev-local-token")}
    response = client.post(
        "/v1/document_register",
        json={"reference": "../../etc/passwd", "document_type": "register"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["stored"]["reference"] == "../../etc/passwd"
