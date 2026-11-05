"""track_loader -- load and validate track files against the shipped schema.

Scope
  READS  the caller's track YAML / track path / track id, and the shipped
         tracks/ directory; then drives the validation and version blocks.
         ``config`` is deliberately not bound: the vendored config block
         initialises against a host HAL the generated adapters do not supply,
         so binding it would make every load fail with an AttributeError.
  WRITES the capability record (the route persists it) and the published
         content version.
  NEVER  invents programme content: a track is refused with the offending
         field path, never repaired. No track name, week theme or rubric text
         appears in this module.
"""

from __future__ import annotations

from typing import Any, Dict

from app import domain, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS
from app.dispatch import execute
from app import programme

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "track_loader"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["validation", "version"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}


def _load(payload: Dict[str, Any]):
    try:
        return programme.resolve(payload), None
    except track_schema.TrackError as exc:
        return None, programme.refusal(
            CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused",
            rejected=exc.as_dict(),
        )


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    resolved, error = _load(data)
    if error is not None:
        return error
    document, catalogue = resolved
    document = document or {}
    track_id = str(document.get("id") or data.get("track_id") or "tracks")
    file_version = str(document.get("file_version") or "v1")
    rubric = document.get("rubric") or {}

    validation_answer = execute(
        "validation",
        {
            "item": {
                "id": track_id,
                "type": "track",
                "name": str(document.get("name") or "catalogue"),
                "length_weeks": int(document.get("length_weeks") or 0),
            },
            "context": {"schema_version": str(document.get("schema_version") or "track.v1")},
        },
        action=BLOCK_DEFAULT_ACTIONS["validation"],
    )
    version_answer = programme.publish_version(
        track_id,
        file_version,
        ["loaded from %s" % (document.get("path") or "tracks/")],
    )

    answers = {
        "validation": validation_answer,
        "version": version_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    stages = validation_answer.get("stages") if isinstance(validation_answer, dict) else None
    record = {
        "reference": domain.text(data.get("reference") or "track-loader-%s" % track_id),
        "status": domain.text(data.get("status") or "open"),
        "track_id": track_id,
        "track_yaml": domain.text(data.get("track_yaml"))[:4000],
        "track_path": domain.text(document.get("path") or data.get("track_path")),
        "schema_version": domain.text(document.get("schema_version") or "track.v1"),
        "name": domain.text(document.get("name")),
        "audience": domain.text(document.get("audience")),
        "length_weeks": domain.integer(document.get("length_weeks")),
        "hours_per_week": domain.number(document.get("hours_per_week")),
        "terms": len(document.get("terms") or []),
        "criteria": len(rubric.get("criteria") or []),
        "points_each": domain.integer(rubric.get("points_each")),
        "weights": dict(rubric.get("weights") or {}),
        "bands": dict(rubric.get("bands") or {}),
        "track_version": file_version,
        "content_version": domain.text(document.get("content_version")),
        "published_version": (version_answer or {}).get("version") or "",
        "validation_stages": stages or [],
        "catalogue": catalogue,
        "tracks": [row.get("id") for row in catalogue] or [track_id],
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        loaded=bool(document),
        catalogueSize=len(catalogue),
    )
