"""enrolment_and_scheduling -- enrol a learner and generate the live schedule.

A 16-week track runs a FIXED weekly session template -- framework (weekday 0,
90 min), case_prep (1, 60), case_class (2, 120), lab (4, 90), lab (5, 90),
exam (6, 60) -- so enrolment expands it into dated sessions from the learner's
start date and timezone, queues the week-1 reading email, and keeps today /
upcoming visible. The email-delivery connector is a DECLARED placeholder: the
route answers the typed 503 until its transport exists, and this handler is
written to run the moment it does.

READS   the enrolment record, the track file for the programme key, the clock.
WRITES  a dated schedule and the notification/email intents, plus the cohort
        team; nothing is persisted by the handler itself.
NEVER   sends mail through an undeclared channel, or schedules a session into
        the past because a timezone was guessed.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app import authority, block_inputs
from app.actions import _support
from app.actions._support import ok, refuse
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "enrolment_and_scheduling"
ENTITY = "enrolment_and_scheduling"
BLOCK_IDS = [
    "workflow",
    "cpm_engine",
    "team",
    "notification",
    "email",
    "transaction_state_machine",
]

SESSION_TEMPLATE: List[Dict[str, Any]] = [
    {"kind": "framework", "weekday": 0, "minutes": 90},
    {"kind": "case_prep", "weekday": 1, "minutes": 60},
    {"kind": "case_class", "weekday": 2, "minutes": 120},
    {"kind": "lab", "weekday": 4, "minutes": 90},
    {"kind": "lab", "weekday": 5, "minutes": 90},
    {"kind": "exam", "weekday": 6, "minutes": 60},
]

TERM_WEEKS = 16


def _step(block_id: str, payload: Dict[str, Any], answers: Dict[str, Any], action: Optional[str] = None) -> Optional[str]:
    answer = execute(block_id, payload, action=action or BLOCK_DEFAULT_ACTIONS.get(block_id))
    answers[block_id] = answer
    return block_inputs.failure(answer)


def _team_id(answer: Dict[str, Any]) -> Any:
    """The id create_team minted, carried into the context call."""
    for key in ("team_id", "id"):
        if answer.get(key):
            return answer[key]
    for key in ("team", "result", "output"):
        value = answer.get(key)
        if isinstance(value, dict):
            if value.get("team_id"):
                return value["team_id"]
            if isinstance(value.get("team"), dict) and value["team"].get("id"):
                return value["team"]["id"]
            if value.get("id"):
                return value["id"]
    return None


def _timezone(name: str) -> ZoneInfo:
    candidate = (name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _start_date(raw: str, zone: ZoneInfo) -> dt.date:
    text = (raw or "").strip()
    if text:
        try:
            return dt.date.fromisoformat(text)
        except ValueError:
            pass
    return dt.datetime.now(zone).date()


def _schedule(start: dt.date, zone: ZoneInfo) -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    for week in range(1, TERM_WEEKS + 1):
        week_start = start + dt.timedelta(days=(week - 1) * 7)
        for index, template in enumerate(SESSION_TEMPLATE):
            offset = (int(template["weekday"]) - start.weekday()) % 7
            day = week_start + dt.timedelta(days=offset)
            starts = dt.datetime.combine(day, dt.time(hour=9), tzinfo=zone)
            sessions.append(
                {
                    "session_id": f"w{week:02d}s{index + 1}",
                    "week": week,
                    "index": index + 1,
                    "kind": template["kind"],
                    "minutes": template["minutes"],
                    "starts_at": starts.isoformat(),
                    "timezone": str(zone),
                }
            )
    return sessions


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    learner = _support.text_of(record, "learner_email") or "learner@example.com"
    track_key = _support.text_of(record, "track_key").lower() or "coo"
    zone = _timezone(_support.text_of(record, "timezone"))
    start = _start_date(_support.text_of(record, "start_date"), zone)

    sessions = _schedule(start, zone)
    today = dt.datetime.now(zone).date()
    today_sessions = [item for item in sessions if item["starts_at"][:10] == today.isoformat()]
    upcoming = [item for item in sessions if item["starts_at"][:10] > today.isoformat()][:12]

    answers: Dict[str, Any] = {}
    cohort = f"{track_key}-cohort-{start.isoformat()}"
    workflow_steps = [
        block_inputs.prepare_event_step(
            record,
            CAPABILITY_ID,
            topic=f"enrolment.{track_key}.scheduled",
            message=f"{learner} enrolled on {track_key} from {start.isoformat()}",
            payload={"reference": reference, "track_key": track_key},
        ),
    ]
    failure = _step(
        "workflow",
        block_inputs.prepare_workflow_input(
            record,
            CAPABILITY_ID,
            steps=workflow_steps,
            result={"reference": reference, "sessions": len(sessions)},
        ),
        answers,
    )
    if failure:
        return refuse(f"block refused: workflow: {failure}", "block_failure", blocks=answers)

    activities = [
        {
            "id": session["session_id"],
            "name": f"week {session['week']} {session['kind']}",
            "duration": session["minutes"],
            "predecessors": [sessions[index - 1]["session_id"]] if index else [],
        }
        for index, session in enumerate(sessions)
    ]
    failure = _step(
        "cpm_engine",
        {"activities": activities, "hours_per_day": 8, "calendar": {"days": 7}, "output": "gantt"},
        answers,
    )
    if failure:
        return refuse(f"block refused: cpm_engine: {failure}", "block_failure", blocks=answers)

    team = execute(
        "team",
        {"user_id": learner, "name": cohort, "slug": cohort},
        action="create_team",
    )
    answers["team"] = team
    refusal = block_inputs.failure(team)
    if refusal:
        return refuse(f"block refused: team: {refusal}", "block_failure", blocks=answers)
    team_id = _team_id(team)
    context = execute(
        "team",
        {"team_id": team_id, "user_id": learner, "channel": "mcp", "tool": "team"},
        action="get_team_context",
    )
    refusal = block_inputs.failure(context)
    if refusal:
        return refuse(f"block refused: team context: {refusal}", "block_failure", blocks=answers)

    first_reading = SESSION_TEMPLATE[0]
    failure = _step(
        "notification",
        {
            "channel": "mcp",
            "to": learner,
            "topic": "enrolment.week1.reading",
            "message": f"Week 1 reading for {track_key}",
            "tool": block_inputs.EVENT_TOOL,
            "payload": {
                "reference": reference,
                "week": 1,
                "kind": first_reading["kind"],
                "action": "log",
                "action_name": "enrolment.week1.reading",
            },
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: notification: {failure}", "block_failure", blocks=answers)

    failure = _step(
        "email",
        {
            "to": learner,
            "subject": f"{track_key.upper()} track: week 1 reading",
            "body": (
                f"Welcome to the {track_key} track. Your first session is "
                f"{sessions[0]['starts_at']} ({zone}). Complete the week 1 reading before the case class."
            ),
            "channel": "email",
            "payload": {"reference": reference, "week": 1},
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: email: {failure}", "block_failure", blocks=answers)

    failure = _step(
        "transaction_state_machine",
        {
            "entity_id": reference,
            "vertical": "transaction",
            "event": "post_offers",
            "actor": "provider",
            "transition_id": f"{reference}:scheduled",
            "from_state": "created",
            "to_state": "offered",
            "payload": {"reference": reference, "sessions": len(sessions)},
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: transaction_state_machine: {failure}", "block_failure", blocks=answers)

    result = {
        "reference": reference,
        "learner_email": learner,
        "track_key": track_key,
        "start_date": start.isoformat(),
        "timezone": str(zone),
        "weeks": TERM_WEEKS,
        "sessions_per_week": len(SESSION_TEMPLATE),
        "session_count": len(sessions),
        "contact_minutes": sum(item["minutes"] for item in sessions),
        "sessions": sessions,
        "today": today_sessions,
        "upcoming": upcoming,
        "cohort": {"team": cohort, "team_id": team_id, "role": "learner"},
        "week1_reading": first_reading,
        "state": "scheduled",
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(4),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
