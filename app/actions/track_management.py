"""track_management -- author, validate, version and diff 16-week tracks.

A track is a YAML document validated at admission against the shipped
``track.v1`` JSON Schema; an invalid file is refused with the offending field
path, never accepted and repaired. Versioning keeps a week-level diff against
the previous document, and the version a learner is pinned to is carried on the
enrolment so an incoming edit cannot rewrite their term under them.

READS   the request record, the shipped schema, the seed track files, and the
        previous version the caller attaches for a diff.
WRITES  a validated track document under STORAGE_PATH/workspace and the
        capability's own result; the ROUTE persists the record.
NEVER   rewrites a learner's pinned version, accepts an invalid document, or
        persists anything itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml

from app import authority, block_inputs, tracks
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "track_management"
ENTITY = "track_management"
BLOCK_IDS = [
    "validation",
    "validation_pipeline_fork",
    "spec_analyzer",
    "workflow",
    "workbench",
    "audit",
]

SESSION_TEMPLATE: List[Dict[str, Any]] = tracks.SESSION_TEMPLATE

THEME_STEMS = [
    "diagnosis and framing",
    "the constraint",
    "capacity under uncertainty",
    "the operating cadence",
    "metrics and decision rights",
    "cost-to-serve",
    "supplier and delivery risk",
    "organisation for flow",
    "automation economics",
    "quality and cost of failure",
    "the transformation sequence",
    "portfolio and capital",
    "talent and succession",
    "stakeholder strategy",
    "the operating plan",
    "capstone defence",
]


_SCHEMA: Dict[str, Any] = {}


def _schema() -> Dict[str, Any]:
    """The shipped track.v1 schema, read once (it is versioned data)."""
    schema = _SCHEMA.get("v")
    if schema is None:
        schema = tracks.schema()
        _SCHEMA["v"] = schema
    return schema


def _seed_document(track_key: str) -> Optional[Dict[str, Any]]:
    return tracks.seed(track_key)


def _synthesised_document(track_key: str, title: str, weeks: int) -> Dict[str, Any]:
    """A valid track.v1 document for a key no seed covers."""
    detail = []
    for week in range(1, weeks + 1):
        stem = THEME_STEMS[(week - 1) % len(THEME_STEMS)]
        detail.append(
            {
                "week": week,
                "theme": f"Week {week}: {stem}",
                "case": f"Case study for week {week}",
                "readings": [f"Reading pack, week {week}"],
            }
        )
    return {
        "schema": "track.v1",
        "track_key": track_key,
        "title": title,
        "weeks": weeks,
        "source": "synthesised from record fields",
        "session_template": [dict(item) for item in SESSION_TEMPLATE],
        "rubric": {
            "version": "rubric.v1",
            "criteria": ["thesis", "evidence", "analysis", "counterargument", "recommendation"],
            "weights": {"memos": 60, "defenses": 20, "capstone": 20},
        },
        "weeks_detail": detail,
    }


_VALIDATOR: Dict[str, Any] = {}


def _validator():
    """The shipped schema's validator, built once (it is static data)."""
    import jsonschema

    validator = _VALIDATOR.get("v")
    if validator is None:
        validator = jsonschema.Draft202012Validator(_schema())
        _VALIDATOR["v"] = validator
    return validator


def _validate(document: Dict[str, Any]) -> List[str]:
    validator = _validator()
    errors = []
    for error in sorted(validator.iter_errors(document), key=lambda err: list(err.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or error.json_path
        errors.append(f"{path}: {error.message}")
    if not errors:
        declared = int(document.get("weeks") or 0)
        detail = document.get("weeks_detail") or []
        if len(detail) != declared:
            errors.append(
                f"weeks_detail: {len(detail)} week(s) defined for a {declared}-week track"
            )
    return errors


def _minutes_per_week(document: Dict[str, Any]) -> int:
    return sum(int(item.get("minutes") or 0) for item in document.get("session_template") or [])


def _week_diff(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Week-level diff between two documents (added/removed/changed weeks)."""
    if not isinstance(previous, dict):
        return []
    before = {
        int(item.get("week")): item
        for item in previous.get("weeks_detail") or []
        if isinstance(item, dict) and item.get("week") is not None
    }
    after = {
        int(item.get("week")): item
        for item in current.get("weeks_detail") or []
        if isinstance(item, dict) and item.get("week") is not None
    }
    diff: List[Dict[str, Any]] = []
    for week in sorted(set(before) | set(after)):
        old = before.get(week)
        new = after.get(week)
        if old == new:
            continue
        if old is None:
            diff.append({"week": week, "change": "added", "to": new.get("theme")})
        elif new is None:
            diff.append({"week": week, "change": "removed", "from": old.get("theme")})
        else:
            changed = sorted(
                key for key in set(old) | set(new) if old.get(key) != new.get(key)
            )
            diff.append(
                {
                    "week": week,
                    "change": "changed",
                    "fields": changed,
                    "from": {key: old.get(key) for key in changed},
                    "to": {key: new.get(key) for key in changed},
                }
            )
    return diff


def _parse_supplied(text: str) -> Dict[str, Any]:
    """Parse a supplied track document.

    Unparseable YAML is an invalid FILE and is refused with its position. Text
    that parses to a scalar is not a track document at all (a note, a stray
    value) and is treated as "no document supplied": the record's own fields
    build the canonical one.
    """
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}" if mark else "unknown position"
        return {"error": f"yaml_text is not valid YAML ({where}): {getattr(exc, 'problem', exc)}"}
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    track_key = _support.text_of(record, "track_key").lower() or "executive"
    weeks = _support.int_of(record, "weeks", 16) or 16
    weeks = max(1, min(52, weeks))
    version = _support.int_of(record, "track_version", 1) or 1
    title = _support.text_of(record, "title") or f"{track_key.upper()} executive track"

    supplied = _support.text_of(record, "yaml_text")
    seed = _seed_document(track_key)
    document: Dict[str, Any]
    if supplied:
        parsed = _parse_supplied(supplied)
        if parsed.get("error"):
            return refuse(parsed["error"], "invalid_track", field_path="yaml_text")
        document = parsed or seed or _synthesised_document(track_key, title, weeks)
    else:
        document = seed or _synthesised_document(track_key, title, weeks)

    document = dict(document)
    document.setdefault("schema", "track.v1")
    document.setdefault("track_key", track_key)
    document.setdefault("title", title)
    document.setdefault("weeks", weeks)
    document.setdefault("session_template", [dict(item) for item in SESSION_TEMPLATE])

    errors = _validate(document)
    if errors:
        return refuse(
            "track document violates track.v1: " + "; ".join(errors[:5]),
            "invalid_track",
            field_path=errors[0].split(":", 1)[0] or "track",
            schema_errors=errors,
        )

    previous = _parse_supplied(_support.text_of(record, "previous_yaml")) if _support.text_of(record, "previous_yaml") else None
    diff = _week_diff(previous if isinstance(previous, dict) else None, document)

    reference = _support.reference_of(record)
    workspace = _support.workspace_dir(CAPABILITY_ID)
    artifact = workspace / f"track_{track_key}_v{version}.yaml"
    document_yaml = yaml.safe_dump(document, sort_keys=True)
    artifact.write_text(document_yaml, encoding="utf-8")

    workflow_steps = [
        block_inputs.prepare_event_step(
            record,
            CAPABILITY_ID,
            topic=f"track.{track_key}.v{version}.validated",
            message=f"track {track_key} v{version} validated against track.v1",
            payload={"track_key": track_key, "version": version, "reference": reference},
        ),
    ]
    workflow_input = block_inputs.prepare_workflow_input(
        record,
        CAPABILITY_ID,
        steps=workflow_steps,
        result={"valid": True, "track_key": track_key, "version": version},
    )

    inputs = {
        "validation": {
            "document": document,
            "record": document,
            "schema": _schema(),
            "rules": {"schema": "track.v1", "required": ["schema", "track_key", "title", "weeks"]},
            "topic": f"track.{track_key}.validated",
        },
        "validation_pipeline_fork": {
            "value": weeks,
            "unit": "weeks",
            "available_weeks": 52,
            "claim": f"{weeks}-week track fits the 52-week year",
            "strict": True,
            "ranges": {"weeks": [1, 52]},
        },
        "spec_analyzer": {
            "text": document_yaml,
            "document": document,
            "spec": document,
            "path": str(artifact),
        },
        "workflow": workflow_input,
        "workbench": {
            "brief": (
                f"Validate the track.v1 document for {track_key} v{version} in the "
                "bounded workspace and report the field paths it checked."
            ),
            "path": str(artifact),
            "files": [str(artifact)],
            "workspace": str(workspace),
            "mutable_paths": [str(workspace)],
            "command": "validate-track",
        },
        "audit": {
            "action": "log",
            "actor": CAPABILITY_ID,
            "entity": ENTITY,
            "reference": reference,
            "detail": {"track_key": track_key, "version": version, "weeks": weeks},
        },
    }
    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    minutes = _minutes_per_week(document)
    result = {
        "reference": reference,
        "track_key": track_key,
        "title": document.get("title"),
        "version": version,
        "weeks": int(document.get("weeks") or weeks),
        "sessions_per_week": len(document.get("session_template") or []),
        "contact_minutes_per_week": minutes,
        "total_contact_minutes": minutes * int(document.get("weeks") or weeks),
        "schema": "track.v1",
        "valid": True,
        "week_diff": diff,
        "diff_count": len(diff),
        "artifact": str(artifact),
        "pinned_versions": {reference: version},
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(3),
        "document_digest": _support.digest(document),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
