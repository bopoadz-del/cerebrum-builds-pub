"""ai_faculty_sessions -- the AI faculty chat, one kernel mode per session.

Six modes (lecture, brief, socratic, sparring, oral_quiz, examiner) map from the
session kind, and the mode decides what the faculty will and will not do:
sparring and socratic REFUSE to draft the learner's deliverable and answer with
questions instead. Every session stores its transcript and exactly one audit
row, so an examiner can later see what the faculty said without trusting the
grader's memory of it.

READS   the session record, the learner's question, the track's week context,
        and the knowledge/memory the blocks return.
WRITES  the transcript and one audit row (through the blocks); the ROUTE
        persists the session record.
NEVER   lets the faculty write the deliverable in sparring/socratic modes, or
        reports success over a block that refused.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import authority, block_inputs, llm
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "ai_faculty_sessions"
ENTITY = "ai_faculty_sessions"
BLOCK_IDS = ["agent_swarm", "sub_agent_runtime", "knowledge", "memory", "audit_chain"]

#: session kind -> the faculty persona that runs it.
PERSONA_BY_KIND = {
    "framework": "chief operating officer in residence",
    "case_prep": "case method coach",
    "case_class": "socratic seminar leader",
    "lab": "sparring partner",
    "exam": "external examiner",
}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    tenant = block_inputs.tenant_scope(record)
    session_kind = _support.text_of(record, "session_kind").lower() or "framework"
    week = max(1, min(16, _support.int_of(record, "week", 1) or 1))
    question = _support.text_of(record, "learner_question") or f"What should I take from week {week}?"
    track_key = _support.text_of(record, "track_key").lower()
    mode = llm.mode_for(session_kind, _support.text_of(record, "kernel_mode"))
    persona = PERSONA_BY_KIND.get(session_kind, "executive faculty")

    inputs: Dict[str, Dict[str, Any]] = {
        "agent_swarm": {
            "task": f"{session_kind} session, week {week}: {question}",
            "mode": mode,
            "agents": [
                {"role": "domain_faculty", "prompt": persona},
                {"role": "evidence_checker", "prompt": "label every claim with its source layer"},
                {"role": "devils_advocate", "prompt": "state the strongest objection"},
            ],
            "reference": reference,
            "topic": f"faculty.{session_kind}.week{week}",
        },
        "sub_agent_runtime": {
            "agent": persona,
            "instruction": question,
            "task": question,
            "payload": {"task": question, "mode": mode, "persona": persona},
            "mode": mode,
            "context": {"week": week, "session_kind": session_kind, "track_key": track_key},
            "tenant_id": tenant,
        },
        "knowledge": {
            "query": question,
            "question": question,
            "topic": f"{session_kind} week {week}",
            "week": week,
            "track_key": track_key,
            "project_id": tenant,
            "top_k": 5,
        },
        "memory": {
            "reference": reference,
            "key": f"faculty.{reference}",
            "value": {"mode": mode, "week": week, "session_kind": session_kind},
        },
        "audit_chain": {
            "action_execution_id": f"{reference}:session:{week}:{session_kind}",
            "action_type": "ai_faculty_session",
            "principal_id": reference,
            "tenant_id": tenant,
            "entity": ENTITY,
            "reference": reference,
            "actor": CAPABILITY_ID,
            "payload": {"mode": mode, "week": week, "session_kind": session_kind},
            "result": {"mode": mode, "week": week},
        },
    }

    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    passages: List[str] = []
    knowledge = answers.get("knowledge") or {}
    for key in ("results", "hits", "passages", "items", "documents"):
        value = knowledge.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("text"):
                    passages.append(str(item["text"]))
                elif isinstance(item, str):
                    passages.append(item)
            break

    reply = llm.faculty_reply(
        mode,
        question,
        session_kind=session_kind,
        week=week,
        track_key=track_key,
        context=passages,
    )
    transcript = [
        {"role": "learner", "text": question, "turn": 1},
        {
            "role": "faculty",
            "text": reply["answer"],
            "mode": mode,
            "turn": 2,
            "refuses_draft": reply.get("refuses_draft", False),
        },
        {"role": "faculty", "text": " ".join(reply.get("followups") or []), "mode": mode, "turn": 3},
    ]
    result = {
        "reference": reference,
        "session_kind": session_kind,
        "kernel_mode": mode,
        "persona": persona,
        "week": week,
        "transcript": transcript,
        "turn_count": len(transcript),
        "refused_to_draft": bool(reply.get("refuses_draft")),
        "refusal_reason": reply.get("refusal_reason"),
        "faculty_version": reply.get("faculty_version"),
        "citations": reply.get("citations", []),
        "audit_rows": 1,
        "audited": (answers.get("audit_chain") or {}).get("ok") is not False,
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(2 if passages else 3),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
