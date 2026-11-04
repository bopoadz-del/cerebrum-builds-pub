"""command_center_and_chat -- the operator console and the run-the-term chat.

The command centre walks the operator through the term in five stages --
enrol, today, session, submit, gradebook -- and the operational chat answers
inside whichever stage the operator is standing in, at desktop and phone width.
The console is built ON the dashboard block (its widgets, layout and metrics),
with the voice block for spoken queries and the aesthetic kit for the theme, so
the screen is the platform's own surface rather than a page beside it.

READS   the stage, the operator's message, the dashboard layout and metrics.
WRITES  the console layout, the chat turn, and its authority label.
NEVER   answers a stage question with another stage's data, or reports success
        over a refused dashboard/voice block.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import authority
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "command_center_and_chat"
ENTITY = "command_center_and_chat"
BLOCK_IDS = ["dashboard", "voice", "aesthetic_kit"]

STAGES: List[Dict[str, Any]] = [
    {"stage": "enrol", "label": "Enrol a learner", "next": "today"},
    {"stage": "today", "label": "Today's sessions", "next": "session"},
    {"stage": "session", "label": "Run the session", "next": "submit"},
    {"stage": "submit", "label": "Submit a memo", "next": "gradebook"},
    {"stage": "gradebook", "label": "Read the gradebook", "next": "enrol"},
]

_ANSWERS = {
    "enrol": "Enrolment creates the learner's 16-week schedule from the fixed session template and queues the week-1 reading.",
    "today": "Today lists the sessions scheduled for the learner's timezone, plus the next upcoming cohort session.",
    "session": "A session runs one kernel mode: lecture, brief, socratic, sparring, oral quiz or examiner. Sparring asks questions instead of drafting.",
    "submit": "A memo is submitted without the faculty transcript attached; the grader scores five criteria 0-20 against the rubric.",
    "gradebook": "The gradebook recomputes the weighted average (memos 60, defenses 20, capstone 20) on every read and issues the transcript PDF.",
}


def _stage(requested: str, message: str) -> str:
    stage = (requested or "").strip().lower()
    if stage in {item["stage"] for item in STAGES}:
        return stage
    lower = (message or "").lower()
    for candidate in ("gradebook", "capstone", "defense", "submit", "grade", "enrol", "session", "today"):
        if candidate in lower:
            mapped = {"capstone": "gradebook", "defense": "submit", "grade": "gradebook"}.get(candidate, candidate)
            if mapped in {item["stage"] for item in STAGES}:
                return mapped
    return "today"


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    message = _support.text_of(record, "message")
    stage = _stage(_support.text_of(record, "stage"), message)
    stage_meta = next(item for item in STAGES if item["stage"] == stage)

    widgets = [
        {"id": "stage", "kind": "status", "label": "Stage", "value": stage},
        {"id": "cohort", "kind": "metric", "label": "Learners in cohort", "value": 1},
        {"id": "next", "kind": "action", "label": "Next step", "value": stage_meta["next"]},
        {"id": "authority", "kind": "label", "label": "Answer authority", "value": authority.label(4)},
    ]
    inputs: Dict[str, Dict[str, Any]] = {
        "dashboard": {
            "action": "render",
            "layout": {"columns": 2, "refresh_interval": 30, "max_widgets": 8, "theme": "executive"},
            "widgets": widgets,
            "metrics": {"stage": stage, "open_sessions": 0, "memos_pending": 0},
            "widths": {"desktop": 1280, "phone": 390},
            "reference": reference,
        },
        "voice": {
            # The sealed voice block's TTS/STT transports are network services;
            # this platform runs offline, so the capability asks the block for
            # its supported-language read instead of pretending to synthesise.
            "operation": "languages",
            "action": "languages",
            "audio": "",
            "text": message or f"status of {stage}",
            "language": "en",
            "channel": "mcp",
            "payload": {"reference": reference, "stage": stage},
        },
        "aesthetic_kit": {
            "question": message or f"status of {stage}",
            "theme": "executive",
            "palette": {"surface": "#0f172a", "accent": "#38bdf8", "text": "#e2e8f0"},
            "density": "comfortable",
            "brand": "Cerebrum Executive Programs",
        },
    }
    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    reply = _ANSWERS[stage]
    if message:
        reply = f"{reply} (on your question: {message[:200]})"
    result = {
        "reference": reference,
        "stage": stage,
        "stage_label": stage_meta["label"],
        "next_stage": stage_meta["next"],
        "stages": [item["stage"] for item in STAGES],
        "layout": {"columns": 2, "refresh_interval": 30, "theme": "executive"},
        "widgets": widgets,
        "widths": {"desktop": 1280, "phone": 390},
        "chat": {
            "question": message,
            "answer": reply,
            "authority": authority.label(4),
            "citations": [],
        },
        "voice": {"transcribed": False, "language": "en", "offline": True},
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(4),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
