"""defense_and_capstone -- term defenses, capstone review and graduation.

Scope
  READS  the track (terms, defense minutes, capstone shape), the learner's
         start date and timezone, the verdicts supplied, and the gradebook
         average; then drives the workflow, notification, approval_rules,
         transaction_state_machine and pdf blocks.
  WRITES the defense date (the term's last day), the pass/fail verdict, the
         re-sit date when the term is failed, the capstone acceptance rule and
         graduation readiness, plus a real PDF schedule.
  NEVER  sends an invite: email delivery is a declared placeholder connector
         and the route answers its typed refusal before this handler runs. It
         never graduates a learner the rule does not pass.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List

from app import domain, programme, schedule, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS, audit_input
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "defense_and_capstone"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["workflow", "notification", "approval_rules", "transaction_state_machine", "pdf"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}

RESIT_DAYS = 7


def _export_dir() -> str:
    root = os.getenv("STORAGE_PATH") or "."
    path = os.path.join(root, "exports")
    os.makedirs(path, exist_ok=True)
    return path


def _acceptance(verdicts: List[str]) -> str:
    """The capstone acceptance rule, stated as data.

    Three verdicts decide: all accept -> accepted; accept/accept/revise ->
    revise; anything else is rejected.
    """
    cleaned = [str(item).strip().lower() for item in verdicts if str(item).strip()]
    if len(cleaned) < 3:
        return "pending"
    accepts = cleaned.count("accept")
    if accepts == 3:
        return "accepted"
    if accepts == 2 and cleaned.count("revise") == 1:
        return "revise"
    return "rejected"


def _term_sessions(term: Dict[str, Any], start: date, timezone_name: str) -> List[Dict[str, Any]]:
    numbers = [int(week.get("number") or 0) for week in term.get("weeks") or []]
    if not numbers:
        return []
    first, last = min(numbers), max(numbers)
    calendar = schedule.generate(start, timezone_name, last)
    return [entry for entry in calendar if first <= entry["week"] <= last]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    try:
        track = track_schema.load_track(str(data.get("track_id") or "").strip() or track_schema.index()[0]["id"])
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")
    except IndexError:
        return programme.refusal(CAPABILITY_ID, "no track files are shipped", field="track_id", kind="schema_refused")

    terms = list(track.get("terms") or [])
    term_number = domain.integer(data.get("term"), 1) or 1
    term = next((entry for entry in terms if int(entry.get("number") or 0) == term_number), None)
    if term is None:
        return programme.refusal(
            CAPABILITY_ID,
            "track %r declares no term %s" % (track.get("id"), term_number),
            field="term",
            kind="schema_refused",
        )

    timezone_name = domain.text(data.get("timezone") or "UTC")
    try:
        start = schedule.parse_start(data.get("start_date"))
        sessions = _term_sessions(term, start, timezone_name)
    except schedule.ScheduleError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field="start_date", kind="schedule_refused")

    defense_date = sessions[-1]["local_date"] if sessions else start.isoformat()
    minutes = domain.integer(data.get("defense_minutes"), domain.integer(term.get("defense_minutes"), 45)) or 45
    kind = domain.text(data.get("kind") or "defense").strip().lower()
    verdict = domain.text(data.get("verdict") or "").strip().lower()
    resit_date = ""
    if kind == "defense" and verdict == "fail":
        resit_date = (date.fromisoformat(defense_date) + timedelta(days=RESIT_DAYS)).isoformat()
    elif kind == "resit":
        resit_date = domain.text(data.get("scheduled_date") or defense_date)

    raw_verdicts = data.get("verdicts")
    if isinstance(raw_verdicts, str) and raw_verdicts.strip():
        raw_verdicts = [part.strip() for part in raw_verdicts.split(",") if part.strip()]
    verdicts = [str(item) for item in raw_verdicts] if isinstance(raw_verdicts, list) else []
    acceptance = _acceptance(verdicts)

    passes = int(data.get("defense_passes") or 0) if str(data.get("defense_passes") or "").isdigit() else 0
    if kind == "defense" and verdict == "pass":
        passes += 1
    average = domain.number(data.get("average"))
    graduation_average = domain.number(os.getenv("PLATFORM_GRADUATION_AVERAGE"), 80.0)
    graduation = bool(
        average >= graduation_average
        and passes >= 4
        and acceptance == "accepted"
    )

    reference = domain.text(
        data.get("reference") or "defense-%s-t%s-%s" % (track.get("id"), term_number, kind)
    )
    learner = domain.text(data.get("learner_email") or "guest@example.com")
    reviewers = [str(item) for item in data.get("reviewers") or [] if str(item).strip()]
    if len(reviewers) < 2:
        reviewers = [learner, "reviewer@example.com"][:2]
    invites = [
        "capstone review invitation: %s for %s (term %s)" % (reviewer, track.get("id"), term_number)
        for reviewer in reviewers[:2]
    ]

    export_root = _export_dir()
    pdf_path = os.path.join(export_root, domain.safe_slug(reference, "defense") + ".pdf")
    domain.write_pdf(
        pdf_path,
        "Term %s defense schedule - %s" % (term_number, domain.text(track.get("name"))),
        [
            "Learner: %s" % learner,
            "Term: %s (%s)" % (term_number, domain.text(term.get("title"))),
            "Defense date: %s (%s minutes, %s)" % (defense_date, minutes, timezone_name),
            "Verdict: %s" % (verdict or "pending"),
            "Re-sit: %s" % (resit_date or "not scheduled"),
            "Capstone acceptance: %s" % acceptance,
            *invites,
        ],
    )

    audit_payload = audit_input(
        {
            "reference": reference,
            "status": "open",
            "principal_id": programme.principal(data),
            "action_name": "defense_and_capstone.%s" % kind,
            "resource_type": "defense_and_capstone",
            "category": "defense",
            "tenant_id": programme.tenant(data),
        }
    )
    workflow_answer = execute(
        "workflow",
        {
            "pipeline_id": "wf-" + reference,
            "steps": [
                {"id": "step_0", "block": "audit", "params": {"action": "log"}, "input": audit_payload}
            ],
        },
        action="run",
    )
    notification_answer = execute(
        "notification",
        {
            "message": "defense scheduled for %s on %s" % (learner, defense_date),
            "channel": "mcp",
            "block": "email",
            "tool": "email",
            "payload": {"reference": reference, "term": term_number},
        },
        action="outbox",
    )
    approval_answer = execute(
        "approval_rules",
        {"project_id": domain.text(track.get("id")), "action": "list"},
        action="list",
    )
    machine_answer = execute(
        "transaction_state_machine",
        {"entity_id": reference, "vertical": "task", "actor": "system", "operation": "machine"},
        action="machine",
    )
    pdf_answer = execute("pdf", {"file_path": pdf_path}, action="extract")

    answers = {
        "workflow": workflow_answer,
        "notification": notification_answer,
        "approval_rules": approval_answer,
        "transaction_state_machine": machine_answer,
        "pdf": pdf_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    extracted = ""
    for key in ("text", "content"):
        value = (pdf_answer or {}).get(key)
        if isinstance(value, str) and value.strip():
            extracted = value
            break

    record = {
        "reference": reference,
        "status": domain.text(data.get("status") or "open"),
        "learner_email": learner,
        "track_id": domain.text(track.get("id")),
        "term": term_number,
        "term_title": domain.text(term.get("title")),
        "kind": kind,
        "scheduled_date": defense_date,
        "defense_minutes": minutes,
        "verdict": verdict,
        "resit_date": resit_date,
        "resit_within_days": RESIT_DAYS if resit_date else None,
        "reviewer_email": reviewers[0] if reviewers else "",
        "reviewers": reviewers[:2],
        "capstone_invites": invites,
        "capstone_verdicts": verdicts,
        "capstone_acceptance": acceptance,
        "defense_passes": passes,
        "average": average,
        "graduation_average_required": graduation_average,
        "graduation_ready": graduation,
        "pdf_path": pdf_path,
        "pdf_characters": len(extracted),
        "email_status": "queued_not_sent_placeholder",
        "authority": {"layer": 1, "label": "certified", "source": "platform_rules"},
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        acceptance=acceptance,
        graduation_ready=graduation,
        resit_date=resit_date,
    )
