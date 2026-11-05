"""Track administration: validation, the week diff, and version pinning."""

from __future__ import annotations

from pathlib import Path

from app import track_schema

ROOT = Path(__file__).resolve().parents[1]


def _admin():
    from app.actions import track_admin

    return track_admin


def _coo_text() -> str:
    return (ROOT / "tracks" / "coo.v1.yaml").read_text(encoding="utf-8")


def test_a_valid_upload_is_accepted_and_diffed():
    result = _admin().handle({"reference": "admin-1", "status": "open", "track_yaml": _coo_text()})
    assert result["ok"] is True
    assert result["record"]["validated"] is True
    assert result["record"]["diff_counts"]["regressed"] == 0
    assert result["record"]["weeks"] == 16


def test_an_edited_week_shows_up_in_the_week_diff():
    edited = _coo_text().replace(
        "theme: Throughput, capacity and the constraint that sets the pace",
        "theme: Throughput, capacity and the constraint that sets the pace (revised)",
    )
    result = _admin().handle({"reference": "admin-2", "status": "open", "track_yaml": edited})
    assert result["ok"] is True
    changes = result["record"]["weeks_changed"]
    assert [entry["week"] for entry in changes] == [1]
    assert changes[0]["fields"] == ["theme"]
    assert changes[0]["status"] == "changed"
    assert result["record"]["diff_counts"]["regressed"] == 1


def test_an_invalid_upload_is_refused_with_the_field_path():
    broken = _coo_text().replace("  points_each: 20", "  points_each: 25")
    result = _admin().handle({"reference": "admin-3", "status": "open", "track_yaml": broken})
    assert result["ok"] is False
    assert result["rejected_field"] == "rubric.points_each"


def test_a_track_is_pinned_per_enrolment():
    result = _admin().handle(
        {
            "reference": "admin-4",
            "status": "open",
            "track_id": "coo",
            "operation": "pin",
            "pinned_version": "v1",
        }
    )
    assert result["ok"] is True
    assert result["record"]["pinned_version"] == "v1"
    assert result["record"]["operation"] == "pin"


def test_the_operation_vocabulary_is_enforced(client, auth):
    resp = client.post(
        "/v1/track_admin",
        json={"reference": "admin-5", "status": "open", "operation": "delete-everything"},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["rejected_field"] == "operation"
    assert "validate" in resp.json()["allowed_values"]


def test_an_unknown_track_is_refused_by_the_loader_not_papered_over():
    try:
        track_schema.load_track("no-such-track")
    except track_schema.TrackError as exc:
        assert exc.field == "track_id"
    else:  # pragma: no cover - the refusal is the contract
        raise AssertionError("an unknown track id was accepted")
