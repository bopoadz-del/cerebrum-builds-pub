"""Memo grading: bands, verdict lines, provenance, and the transcript wall."""

from __future__ import annotations

import inspect

from app import grading, track_schema

_PARAGRAPHS = [
    (
        "Problem diagnosis: the operating problem in this plant is the constraint that "
        "sets the pace, and the measures we report hide it. The Goal puts that constraint "
        "first, and The Machine That Changed the World makes the same point about the "
        "world of work. In the case, utilisation looked healthy while delivery dates "
        "slipped, because the plant measured busy-ness rather than flow. Diagnosis: the "
        "furnace is the binding constraint and every other cell is capacity the constraint "
        "cannot use."
    ),
    (
        "Evidence and sources: the evidence is the queue length in front of the furnace, "
        "measured hourly, and the sources are the week's readings. The Goal supplies the "
        "mechanism and The Machine That Changed the World supplies the value-stream claim. "
        "The case is a plant whose utilisation looked healthy while delivery dates slipped. "
        "What is not known is the changeover distribution, so I do not claim a second "
        "furnace is unnecessary."
    ),
    (
        "Causal mechanism: the mechanism is a queue in front of the constraint, so "
        "releasing more work upstream cannot raise output. The Goal is explicit that the "
        "constraint sets the pace and everything else is subordinated to it, and The "
        "Machine That Changed the World shows the same mechanism at the level of the whole "
        "value stream. The plant in the case measured busy-ness, so utilisation rose while "
        "delivery dates slipped. That is the observable signature of this mechanism."
    ),
    (
        "Decision and trade-offs: the decision is to cap release at the furnace's takt "
        "this quarter. The alternative given up is a higher utilisation figure in the "
        "machining cells, which is what The Goal says to give up when it is not the "
        "constraint. The Machine That Changed the World supports the value-stream framing "
        "of that trade-off. I would reverse this if the changeover time at the furnace "
        "falls below twenty minutes."
    ),
    (
        "Executive communication: the ask is one decision, cap release at the constraint, "
        "and the risk is a lower utilisation report this quarter. The Goal and The Machine "
        "That Changed the World are named so the board can check the reasoning. The case "
        "is cited because its plant looked healthy on utilisation while delivery dates "
        "slipped. The evidence is hourly queue length, and the limit is the changeover "
        "distribution we have not measured."
    ),
]

STRONG = "\n\n".join(_PARAGRAPHS)

WEAK = (
    "I think the case was interesting. The company should probably do better next "
    "time. This is my memo for the week."
)

EMPTY = ""


def _grade(submission: str):
    track = track_schema.load_track("coo")
    week = track_schema.week_of(track, 1)
    return track, grading.grade(track, 1, submission, week=week)


def test_a_strong_memo_reaches_band_a():
    _track, result = _grade(STRONG)
    assert result["ok"] is True
    assert result["total"] >= 90
    assert result["band"] == "A"
    assert result["rewrite_required"] is False


def test_a_weak_memo_takes_the_rewrite_path():
    _track, result = _grade(WEAK)
    assert result["ok"] is True
    assert result["total"] < 70
    assert result["rewrite_required"] is True


def test_an_empty_memo_is_graded_zero_and_rewritten():
    _track, result = _grade(EMPTY)
    assert result["ok"] is True
    assert result["total"] == 0
    assert result["band"] == "C"
    assert result["rewrite_required"] is True


def test_one_verdict_line_per_rubric_criterion():
    track, result = _grade(STRONG)
    criteria = track["rubric"]["criteria"]
    assert len(result["verdict_lines"]) == len(criteria) == 5
    for line, criterion in zip(result["verdict_lines"], criteria):
        assert line.startswith(criterion["id"] + ":")
        assert "/20" in line


def test_provenance_names_the_block_version_rubric_and_run():
    track, result = _grade(STRONG)
    provenance = result["provenance"]
    assert provenance["kernel_block"] == "formula_executor"
    assert provenance["kernel_version"]
    assert provenance["rubric_version"] == track["content_version"]
    assert len(provenance["run_id"]) == 32
    assert provenance["transcript_access"] == "none"


def test_the_grader_has_no_transcript_access():
    source = inspect.getsource(grading)
    assert "faculty_session" not in source
    assert "app.actions" not in source
    tree = __import__("ast").parse(source)
    imported = set()
    for node in __import__("ast").walk(tree):
        if isinstance(node, __import__("ast").ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, __import__("ast").Import):
            imported.update(alias.name for alias in node.names)
    assert not any("faculty" in name for name in imported)
    result = grading.grade(
        track_schema.load_track("coo"),
        1,
        STRONG,
        week=track_schema.week_of(track_schema.load_track("coo"), 1),
    )
    assert "transcript" not in result


def test_the_route_grades_a_memo_and_records_the_verdicts(client, auth):
    resp = client.post(
        "/v1/memo_grading",
        json={
            "reference": "memo-strong",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "learner_email": "learner@example.com",
            "submission": STRONG,
        },
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    record = body["record"]
    assert record["band"] == "A"
    assert len(record["verdict_lines"]) == 5
    assert record["provenance"]["run_id"]
    assert record["transcript_access"] == "none"
    assert body["id"] == record["id"]


def test_a_rubric_version_the_caller_pins_is_the_one_recorded(client, auth):
    resp = client.post(
        "/v1/memo_grading",
        json={
            "reference": "memo-pinned",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "submission": WEAK,
            "rubric_version": "coo-rubric-2026-01",
        },
        headers=auth,
    )
    record = resp.json()["record"]
    assert record["provenance"]["rubric_version"] == "coo-rubric-2026-01"
    assert record["rewrite_required"] is True
