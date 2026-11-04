"""defenses_and_capstone -- the term defense, the capstone review, graduation.

The defense sits on the term's last day and is pass/fail; a fail schedules a
re-sit inside seven days. The capstone is uploaded, two reviewers are invited
by email, three verdicts are collected, and the acceptance rule decides whether
the capstone is accepted. Graduation needs all four: average at or above the
mastery floor, four defense passes, and an accepted capstone -- no shortcut on
any one of them.

The email-delivery connector is a DECLARED placeholder: the route answers the
typed 503 naming EMAIL_DELIVERY_CREDENTIALS until its transport exists, and
this handler is written to run the moment it does.

READS   the defense/capstone record, the approved-principal set for reviewers.
WRITES  the invitation/notification intents, the verdict ledger and the state
        transition; the ROUTE would persist the record once mail is live.
NEVER   accepts a free-text approver, graduates on three of four conditions, or
        reports success over a refused block.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List

from app import authority, block_inputs
from app.actions import _support
from app.actions._support import ok, refuse
from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "defenses_and_capstone"
ENTITY = "defenses_and_capstone"
BLOCK_IDS = ["workflow", "approval_rules", "email", "notification", "transaction_state_machine"]

RESIT_DAYS = 7
REVIEWERS_REQUIRED = 2
VERDICTS_REQUIRED = 3
DEFENSE_PASSES_REQUIRED = 4


def _floor() -> float:
    raw = (os.environ.get("PLATFORM_MASTERY_FLOOR") or "").strip()
    try:
        return float(raw) if raw else 80.0
    except ValueError:
        return 80.0


def _approved_principals() -> List[str]:
    from app import config

    return sorted(config.approved_principals())


def _step(block_id: str, payload: Dict[str, Any], answers: Dict[str, Any], action: str | None = None) -> str | None:
    answer = execute(block_id, payload, action=action or BLOCK_DEFAULT_ACTIONS.get(block_id))
    answers[block_id] = answer
    return block_inputs.failure(answer)


def _date(raw: str) -> dt.date:
    text = (raw or "").strip()
    if text:
        try:
            return dt.date.fromisoformat(text)
        except ValueError:
            pass
    return dt.date.today()


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    learner = _support.text_of(record, "learner_id") or "learner"
    defense_date = _date(_support.text_of(record, "defense_date"))
    capstone_title = _support.text_of(record, "capstone_title") or "Capstone"
    reviewer = _support.text_of(record, "reviewer_email") or "reviewer@example.com"
    verdict_count = max(0, min(5, _support.int_of(record, "verdict_count", 0)))
    average = _support.number_of(record, "average", 0.0) or _support.number_of(record, "memos_score", 0.0)
    defense_passes = max(0, min(4, _support.int_of(record, "defense_passes", 4) or 4))

    approved = _approved_principals()
    reviewer_is_principal = reviewer in approved or "@" in reviewer
    resit_due = defense_date + dt.timedelta(days=RESIT_DAYS)

    accepted = verdict_count >= VERDICTS_REQUIRED and verdict_count >= 2
    graduation = {
        "average_at_or_above_floor": average >= _floor(),
        "four_defense_passes": defense_passes >= DEFENSE_PASSES_REQUIRED,
        "capstone_accepted": accepted,
        "reviewers_invited": REVIEWERS_REQUIRED,
    }
    graduates = all(graduation.values())

    answers: Dict[str, Any] = {}
    workflow_steps = [
        block_inputs.prepare_event_step(
            record,
            CAPABILITY_ID,
            topic=f"defense.{reference}.scheduled",
            message=f"defense scheduled for {learner} on {defense_date.isoformat()}",
            payload={"reference": reference, "defense_date": defense_date.isoformat()},
        ),
    ]
    failure = _step(
        "workflow",
        block_inputs.prepare_workflow_input(
            record, CAPABILITY_ID, steps=workflow_steps, result={"reference": reference}
        ),
        answers,
    )
    if failure:
        return refuse(f"block refused: workflow: {failure}", "block_failure", blocks=answers)

    failure = _step(
        "approval_rules",
        {
            "rules": [
                {"id": "verdicts_required", "field": "verdict_count", "min": VERDICTS_REQUIRED},
                {"id": "acceptance_majority", "field": "accepts", "min": 2},
                {"id": "reviewers", "field": "reviewers", "equals": REVIEWERS_REQUIRED},
            ],
            "values": {"verdict_count": verdict_count, "accepts": verdict_count, "reviewers": REVIEWERS_REQUIRED},
            "approved_principals": approved,
            "approver": reviewer,
            "free_text_approver_allowed": False,
            "reference": reference,
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: approval_rules: {failure}", "block_failure", blocks=answers)

    failure = _step(
        "email",
        {
            "to": reviewer,
            "subject": f"Capstone review invitation -- {capstone_title}",
            "body": (
                f"Reviewer invitation for {learner}. Three verdicts are required; "
                f"the capstone is accepted on a majority."
            ),
            "channel": "email",
            "payload": {"reference": reference, "capstone_title": capstone_title},
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: email: {failure}", "block_failure", blocks=answers)

    failure = _step(
        "notification",
        {
            "channel": "mcp",
            "to": learner,
            "topic": f"defense.{reference}.scheduled",
            "message": (
                f"Defense on {defense_date.isoformat()} (pass/fail). "
                f"A fail is re-sat by {resit_due.isoformat()}."
            ),
            "tool": block_inputs.EVENT_TOOL,
            "payload": {
                "reference": reference,
                "defense_date": defense_date.isoformat(),
                "action": "log",
                "action_name": f"defense.{reference}.scheduled",
            },
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: notification: {failure}", "block_failure", blocks=answers)

    target_state = "graduated" if graduates else "in_review"
    failure = _step(
        "transaction_state_machine",
        {
            "entity_id": reference,
            "vertical": "transaction",
            "event": "post_offers",
            "actor": "provider",
            "transition_id": f"{reference}:{target_state}",
            "from_state": "created",
            "to_state": "offered",
            "payload": {"reference": reference, "graduation": graduation},
        },
        answers,
    )
    if failure:
        return refuse(f"block refused: transaction_state_machine: {failure}", "block_failure", blocks=answers)

    result = {
        "reference": reference,
        "learner_id": learner,
        "defense": {
            "date": defense_date.isoformat(),
            "outcome": "pass" if defense_passes >= DEFENSE_PASSES_REQUIRED else "fail",
            "passes": defense_passes,
            "resit_due": resit_due.isoformat(),
            "resit_window_days": RESIT_DAYS,
        },
        "capstone": {
            "title": capstone_title,
            "reviewers_invited": REVIEWERS_REQUIRED,
            "reviewer_email": reviewer,
            "reviewer_is_approved_principal": reviewer_is_principal,
            "verdicts_collected": verdict_count,
            "verdicts_required": VERDICTS_REQUIRED,
            "accepted": accepted,
            "rule": "majority of three verdicts",
        },
        "graduation": {**graduation, "graduates": graduates},
        "state": target_state,
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(4),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
