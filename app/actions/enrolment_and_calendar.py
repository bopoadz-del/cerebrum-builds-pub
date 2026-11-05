"""enrolment_and_calendar -- enrol a learner and generate their 96 sessions.

Scope
  READS  the track file (validated), the start date, the learner's timezone,
         and the fixed session template; then drives the auth, notification,
         email and database blocks.
  WRITES the enrolment record, its pinned track version and the full
         calendar the route persists.
  NEVER  sends the week-1 reading email here: email delivery is a declared
         placeholder connector and the route answers its typed refusal before
         this handler runs. The message this module composes is the one that
         will be sent when the connector exists.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain, schedule, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS
from app.dispatch import execute
from app import programme

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "enrolment_and_calendar"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["auth", "notification", "email", "database"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}


def _email_body(track: Dict[str, Any], week_one: Dict[str, Any]) -> str:
    readings = [str(item.get("title") or "") for item in week_one.get("readings") or []]
    lines = [
        "Welcome to %s." % domain.text(track.get("name")),
        "",
        "Week 1 - %s" % domain.text(week_one.get("theme")),
        "Readings: %s" % ("; ".join(title for title in readings if title) or "see the track file"),
        "Your first session is the framework session on day 0 of week 1.",
    ]
    return "\n".join(lines)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    try:
        track = track_schema.load_track(
            str(data.get("track_id") or "").strip() or track_schema.index()[0]["id"]
        )
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")
    except IndexError:
        return programme.refusal(
            CAPABILITY_ID, "no track files are shipped under tracks/", field="track_id", kind="schema_refused"
        )

    timezone_name = domain.text(data.get("timezone") or "UTC")
    length_weeks = int(track.get("length_weeks") or schedule.DEFAULT_LENGTH_WEEKS)
    try:
        calendar = schedule.generate(data.get("start_date"), timezone_name, length_weeks)
    except schedule.ScheduleError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field="timezone", kind="schedule_refused")

    terms: List[Dict[str, Any]] = list(track.get("terms") or [])
    for entry in calendar:
        term = schedule.term_for_week(terms, entry["week"]) or {}
        entry["term"] = int(term.get("number") or 0)
        entry["term_title"] = domain.text(term.get("title"))
        entry["mode"] = {
            "framework": "lecture",
            "case_prep": "brief",
            "case_class": "socratic",
            "lab": "sparring",
            "exam": "oral_quiz",
        }.get(entry["kind"], "examiner")

    week_one = {}
    for week in (terms[0].get("weeks") if terms else []) or []:
        if int(week.get("number") or 0) == 1:
            week_one = week
            break
    if not week_one and terms:
        week_one = (terms[0].get("weeks") or [{}])[0]

    learner_email = domain.text(data.get("learner_email") or "guest@example.com")
    tenant_id = programme.tenant(data)
    email_text = _email_body(track, week_one)

    auth_answer = execute(
        "auth",
        {"owner": tenant_id, "name": learner_email},
        action="list_keys",
    )
    notification_answer = execute(
        "notification",
        {
            "message": "week-1 reading email queued for %s" % learner_email,
            "channel": "mcp",
            "to": learner_email,
            "subject": "Week 1 readings",
            "block": "email",
            "tool": "email",
            "payload": {"track_id": track.get("id"), "week": 1},
        },
        action="outbox",
    )
    email_answer = execute(
        "email",
        {"email": learner_email, "to": learner_email, "subject": "Week 1 readings", "body": email_text},
        action="validate_address",
    )
    database_answer = execute(
        "database",
        {"table": "enrolment_and_calendar"},
        action="list_tables",
    )

    answers = {
        "auth": auth_answer,
        "notification": notification_answer,
        "email": email_answer,
        "database": database_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    record = {
        "reference": domain.text(data.get("reference") or "enrol-%s" % learner_email),
        "status": domain.text(data.get("status") or "open"),
        "learner_name": domain.text(data.get("learner_name")),
        "learner_email": learner_email,
        "track_id": domain.text(track.get("id")),
        "track_version": domain.text(track.get("file_version")),
        "content_version": domain.text(track.get("content_version")),
        "start_date": calendar[0]["local_date"] if calendar else "",
        "timezone": timezone_name,
        "sessions": len(calendar),
        "week_one_theme": domain.text(week_one.get("theme")),
        "week_one_readings": [str(item.get("title") or "") for item in week_one.get("readings") or []],
        "email_subject": "Week 1 readings",
        "email_body": email_text,
        "email_status": "queued_not_sent_placeholder",
        "calendar": calendar,
        "terms": [
            {
                "number": int(term.get("number") or index + 1),
                "title": domain.text(term.get("title")),
                "weeks": len(term.get("weeks") or []),
                "defense_minutes": domain.integer(term.get("defense_minutes")),
                "defense_date": schedule.term_last_day(calendar, int(term.get("number") or index + 1)),
            }
            for index, term in enumerate(terms)
        ],
    }
    return domain.ok(CAPABILITY_ID, record, answers, outline=schedule.outline(calendar))
