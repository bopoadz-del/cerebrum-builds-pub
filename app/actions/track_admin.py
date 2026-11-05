"""track_admin -- upload, validate, diff and pin a track version.

Scope
  READS  the uploaded YAML, the currently shipped version of the same track,
         and the pinned version named by the caller; then drives the
         validation, version_diff and audit blocks.
  WRITES the validated track, a week-level diff against the current version,
         and the pinned version an enrolment keeps.
  NEVER  writes a track file into the package or re-validates with a second,
         softer rule. ``workbench`` is deliberately not bound: it shells out
         to an agent CLI that is not part of the delivered image, and a
         capability that calls it would fail on every request in production.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain, programme, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS, audit_input
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "track_admin"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["validation", "version_diff", "audit"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}


class WeekFinding:
    """A week as a finding the version_diff block can bucket."""

    def __init__(self, number: int, kind: str, theme: str, detail: Dict[str, Any] | None = None):
        self.element_a = "week"
        self.element_b = "%02d" % int(number)
        self.kind = kind
        self.number = int(number)
        self.theme = theme
        self.detail = dict(detail or {})

    def as_dict(self) -> Dict[str, Any]:
        return {"week": self.number, "theme": self.theme, "kind": self.kind, **self.detail}


def _weeks(document: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for term in document.get("terms") or []:
        for week in term.get("weeks") or []:
            out[int(week.get("number") or 0)] = week
    return out


def _week_shape(week: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "theme": str(week.get("theme") or ""),
        "concepts": [str(item) for item in week.get("concepts") or []],
        "readings": [str((item or {}).get("title") or "") for item in week.get("readings") or []],
        "cases": [str((item or {}).get("title") or "") for item in week.get("cases") or []],
    }


def _diff(current: Dict[str, Any], uploaded: Dict[str, Any]) -> tuple[List[WeekFinding], List[WeekFinding], List[Dict[str, Any]]]:
    before = _weeks(current)
    after = _weeks(uploaded)
    baseline: List[WeekFinding] = []
    proposed: List[WeekFinding] = []
    changes: List[Dict[str, Any]] = []
    for number in sorted(set(before) | set(after)):
        old = before.get(number)
        new = after.get(number)
        old_shape = _week_shape(old) if old else {}
        new_shape = _week_shape(new) if new else {}
        changed = old_shape != new_shape
        baseline.append(
            WeekFinding(number, "clear", old_shape.get("theme", ""), {"theme": old_shape.get("theme", "")})
        )
        proposed.append(
            WeekFinding(
                number,
                "clash" if changed else "clear",
                new_shape.get("theme", ""),
                {"theme": new_shape.get("theme", ""), "changed": changed},
            )
        )
        if not changed:
            continue
        fields = [
            name
            for name in ("theme", "concepts", "readings", "cases")
            if old_shape.get(name) != new_shape.get(name)
        ]
        changes.append(
            {
                "week": number,
                "fields": fields,
                "before": {name: old_shape.get(name) for name in fields},
                "after": {name: new_shape.get(name) for name in fields},
                "status": "changed" if old and new else ("added" if new else "removed"),
            }
        )
    return baseline, proposed, changes


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    operation = domain.text(data.get("operation") or "validate").strip().lower()
    text = domain.text(data.get("track_yaml"))

    try:
        if text.strip():
            uploaded = track_schema.validate_text(text)
        else:
            track_id = str(data.get("track_id") or "").strip()
            if not track_id:
                catalogue = track_schema.index()
                if not catalogue:
                    return programme.refusal(
                        CAPABILITY_ID,
                        "no track files are shipped under tracks/",
                        field="track_yaml",
                        kind="schema_refused",
                    )
                track_id = catalogue[0]["id"]
            uploaded = track_schema.load_track(track_id)
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")

    track_id = str(uploaded.get("id") or data.get("track_id") or "").strip()
    try:
        current = track_schema.load_track(track_id)
    except track_schema.TrackError:
        current = {}

    baseline, proposed, changes = _diff(current, uploaded) if current else ([], [], [])
    pinned = domain.text(data.get("pinned_version") or (current or uploaded).get("file_version") or "v1")

    validation_answer = execute(
        "validation",
        {
            "item": {
                "id": track_id,
                "type": "track",
                "name": str(uploaded.get("name") or ""),
                "length_weeks": int(uploaded.get("length_weeks") or 0),
            },
            "context": {"operation": operation},
        },
        action="validate_pipeline",
    )
    diff_answer = execute(
        "version_diff",
        {"findings_v1": baseline, "findings_v2": proposed, "action": "diff"},
        action="diff",
    )
    audit_answer = execute(
        "audit",
        audit_input(
            {
                "reference": domain.text(data.get("reference") or "track-admin-%s" % track_id),
                "status": "open",
                "principal_id": programme.principal(data),
                "action_name": "track_admin.%s" % operation,
                "resource_type": "track",
                "category": "administration",
                "tenant_id": programme.tenant(data),
            }
        ),
        action="log",
    )

    answers = {"validation": validation_answer, "version_diff": diff_answer, "audit": audit_answer}
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    # The block answers the buckets directly when its result has no envelope
    # of its own; take them from wherever this build's answer puts them.
    buckets = {}
    if isinstance(diff_answer, dict):
        if any(name in diff_answer for name in ("new", "resolved", "regressed", "persisting")):
            buckets = diff_answer
        elif isinstance(diff_answer.get("result"), dict):
            buckets = diff_answer["result"]
    counts = {name: len(buckets.get(name) or []) for name in ("new", "resolved", "regressed", "persisting")}

    record = {
        "reference": domain.text(data.get("reference") or "track-admin-%s" % track_id),
        "status": domain.text(data.get("status") or "open"),
        "track_id": track_id,
        "track_yaml": text[:4000],
        "operation": operation,
        "pinned_version": pinned,
        "uploaded_version": domain.text(uploaded.get("file_version") or "v1"),
        "current_version": domain.text((current or {}).get("file_version") or ""),
        "validated": True,
        "weeks_changed": changes,
        "diff_counts": counts,
        "weeks": len(_weeks(uploaded)),
        "criteria": len((uploaded.get("rubric") or {}).get("criteria") or []),
        "weights": dict((uploaded.get("rubric") or {}).get("weights") or {}),
        "authority": {"layer": 1, "label": "certified", "source": "platform_rules"},
    }
    return domain.ok(CAPABILITY_ID, record, answers, week_diff=changes, diff_counts=counts)
