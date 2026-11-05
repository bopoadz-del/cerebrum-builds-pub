"""Track files: the shipped schema, the seeds, and the refusals it makes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import track_schema

ROOT = Path(__file__).resolve().parents[1]


def _seed(name: str) -> dict:
    text = (ROOT / "tracks" / name).read_text(encoding="utf-8")
    return track_schema.validate_text(text)


def _replace(document: dict, **changes) -> dict:
    copy = json.loads(json.dumps(document))
    copy.update(changes)
    return copy


def test_both_seed_tracks_load_and_validate():
    catalogue = track_schema.index()
    ids = [entry["id"] for entry in catalogue]
    assert ids == ["ceo", "coo"]
    for entry in catalogue:
        assert entry["length_weeks"] == 16
        assert entry["terms"] == 4
        assert entry["criteria"] == 5
        assert entry["weights"] == {"memos": 60, "defenses": 20, "capstone": 20}
        assert entry["version"] == "v1"


def test_missing_rubric_is_refused_naming_rubric():
    document = _replace(_seed("coo.v1.yaml"))
    document.pop("rubric")
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "rubric"
    assert "rubric" in str(excinfo.value)


def test_weights_that_do_not_sum_to_100_are_refused():
    document = _replace(_seed("coo.v1.yaml"))
    document["rubric"]["weights"] = {"memos": 60, "defenses": 20, "capstone": 30}
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "rubric.weights"


def test_a_rubric_with_four_criteria_is_refused():
    document = _replace(_seed("coo.v1.yaml"))
    document["rubric"]["criteria"] = document["rubric"]["criteria"][:4]
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "rubric.criteria"


def test_length_weeks_below_the_minimum_is_refused():
    document = _replace(_seed("coo.v1.yaml"), length_weeks=3)
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "length_weeks"


def test_an_unknown_field_is_refused_by_name():
    document = _replace(_seed("coo.v1.yaml"))
    document["week_theme"] = "a field the schema does not declare"
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "week_theme"


def test_a_gap_in_week_numbers_is_refused():
    document = _replace(_seed("coo.v1.yaml"))
    document["terms"][0]["weeks"][1]["number"] = 99
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.validate(document)
    assert excinfo.value.field == "terms"


def test_unknown_track_id_is_refused_with_its_field():
    with pytest.raises(track_schema.TrackError) as excinfo:
        track_schema.load_track("no-such-track")
    assert excinfo.value.field == "track_id"


def test_a_track_path_outside_tracks_is_refused_by_the_capability(client, auth):
    resp = client.post(
        "/v1/track_loader",
        json={"reference": "ref-1", "status": "open", "track_path": "../../etc/passwd"},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["rejected_field"] == "track_path"
