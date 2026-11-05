"""reading_and_case_library -- per-week readings and cases, outcome withheld.

Scope
  READS  the track's week record (readings, cases, public sources), the
         learner's enrolment date and timezone, and the tenant corpus; then
         drives the knowledge, vector_search and governance_gate blocks.
  WRITES the week's reading list, each case with its public source, and the
         case outcome only once that learner's case_class session has opened.
  NEVER  invents a source or reveals an outcome early: the outcome is withheld
         by comparing the learner's own calendar, not by trusting a request.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from app import domain, programme, schedule, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "reading_and_case_library"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["knowledge", "vector_search", "governance_gate"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}

CASE_CLASS_OFFSET = 2


def _open_date(start: Any, timezone_name: str, week: int) -> str:
    calendar = schedule.generate(start, timezone_name, week)
    for entry in calendar:
        if entry["week"] == week and entry["kind"] == "case_class":
            return entry["local_date"]
    return ""


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    try:
        track = track_schema.load_track(str(data.get("track_id") or "").strip() or track_schema.index()[0]["id"])
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")
    except IndexError:
        return programme.refusal(CAPABILITY_ID, "no track files are shipped", field="track_id", kind="schema_refused")

    week_number = domain.integer(data.get("week"), 1) or 1
    try:
        week = track_schema.week_of(track, week_number)
        term = track_schema.term_of_week(track, week_number)
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")

    timezone_name = domain.text(data.get("timezone") or "UTC")
    try:
        opened_on = _open_date(data.get("start_date"), timezone_name, week_number)
    except schedule.ScheduleError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field="start_date", kind="schedule_refused")
    today = schedule.parse_start(date.today()).isoformat()
    requested_offset = domain.integer(data.get("session_offset"), -1)
    # The date opens the outcome for everyone; the session offset only lets
    # programme staff preview a case they are about to teach. A learner
    # cannot unlock a case outcome early by sending a larger offset.
    by_date = bool(opened_on) and today >= opened_on
    staff_preview = programme.is_staff(data) and requested_offset >= CASE_CLASS_OFFSET
    opened = bool(opened_on) and (by_date or staff_preview)

    readings = [
        {
            "title": domain.text(item.get("title")),
            "source": domain.text(item.get("source")),
            "note": domain.text(item.get("note")),
        }
        for item in week.get("readings") or []
    ]
    cases: List[Dict[str, Any]] = []
    for item in week.get("cases") or []:
        entry = {
            "id": domain.text(item.get("id")),
            "title": domain.text(item.get("title")),
            "source": domain.text(item.get("source")),
            "prompt": domain.text(item.get("prompt")),
            "outcome": domain.text(item.get("outcome")) if opened else "",
            "outcome_withheld": not opened,
        }
        cases.append(entry)

    reference = domain.text(data.get("reference") or "library-%s-w%s" % (track.get("id"), week_number))
    tenant_id = programme.tenant(data)
    theme = domain.text(week.get("theme"))

    knowledge_answer = execute(
        "knowledge",
        {"query": theme, "top_k": 5, "project_id": tenant_id},
        action="search",
    )
    documents = [
        "%s - %s" % (item["title"], item["source"]) for item in readings + cases if item["title"]
    ]
    added_answer = execute(
        "vector_search",
        {"documents": documents or [theme]},
        action="add",
        params={"collection": "week-%s-%s" % (track.get("id"), week_number)},
    )
    search_answer = execute(
        "vector_search",
        {"query": theme},
        action="search",
        params={"collection": "week-%s-%s" % (track.get("id"), week_number), "n_results": 5},
    )
    governance_answer = execute(
        "governance_gate",
        {"tenant_id": tenant_id, "action_type": "reading_and_case_library", "target_id": reference},
        action="list_requests",
    )

    answers = {
        "knowledge": knowledge_answer,
        "vector_search": search_answer,
        "governance_gate": governance_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    record = {
        "reference": reference,
        "status": domain.text(data.get("status") or "open"),
        "learner_email": domain.text(data.get("learner_email") or "guest@example.com"),
        "track_id": domain.text(track.get("id")),
        "track_version": domain.text(track.get("file_version")),
        "week": week_number,
        "term": int(term.get("number") or 0),
        "week_theme": theme,
        "case_id": domain.text(data.get("case_id")),
        "session_offset": requested_offset if requested_offset >= 0 else None,
        "case_class_opens_on": opened_on,
        "outcome_released": opened,
        "readings": readings,
        "cases": cases,
        "concepts": [str(item) for item in week.get("concepts") or []],
        "search_hits": len((search_answer or {}).get("results") or []) if isinstance(search_answer, dict) else 0,
        "indexed_documents": len(documents),
        "authority": {"layer": 2, "label": "documents", "source": "tenant_corpus"},
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        outcome_released=opened,
        case_class_opens_on=opened_on,
    )
