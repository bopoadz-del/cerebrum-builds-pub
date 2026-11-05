"""faculty_session -- a chat session in one of the six kernel modes.

Scope
  READS  the track file and the week record for the session, the learner's
         message, and the tenant's own corpus; then drives the knowledge,
         memory, audit and governance_gate blocks. ``orchestrator`` is not
         bound: the vendored orchestrator only chains blocks through a
         platform registry the generated adapter never wires, so every chain
         it is given is refused before a child runs.
  WRITES the transcript, one audit row per session, and the capability
         record the route persists.
  NEVER  invents faculty content: every turn is composed from the week
         record (see app/llm.py). Sparring mode never writes the learner's
         deliverable -- it returns a refusal instead, whatever the request
         says.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain, llm, programme, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS, audit_input
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "faculty_session"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["knowledge", "memory", "audit", "governance_gate"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    mode = domain.text(data.get("mode") or "lecture").strip().lower()
    if mode not in llm.MODES:
        return programme.refusal(
            CAPABILITY_ID,
            "mode must be one of: %s" % ", ".join(llm.MODES),
            field="mode",
            allowed_values=list(llm.MODES),
        )
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

    message = domain.text(data.get("message"))
    try:
        composed = llm.compose(mode, week, track, message)
    except llm.FacultyError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field="week", kind="schema_refused")

    reference = domain.text(data.get("reference") or "session-%s-w%s-%s" % (track.get("id"), week_number, mode))
    tenant_id = programme.tenant(data)
    principal = programme.principal(data)
    learner = domain.text(data.get("learner_email") or "guest@example.com")

    transcript: List[Dict[str, Any]] = [llm.transcript_entry("learner", message)]
    transcript.extend(llm.transcript_entry("faculty", turn) for turn in composed["turns"])

    knowledge_answer = execute(
        "knowledge",
        {
            "query": "%s %s" % (domain.text(week.get("theme")), message),
            "top_k": 3,
            "project_id": tenant_id,
        },
        action="search",
    )
    memory_answer = execute(
        "memory",
        {
            "key": "faculty:%s" % reference,
            "value": {"mode": mode, "turns": len(transcript), "week": week_number},
            "ttl": 86400,
        },
        action="set",
    )
    audit_payload = audit_input(
        {
            "reference": reference,
            "status": "open",
            "principal_id": principal,
            "action_name": "faculty_session.%s" % mode,
            "resource_type": "faculty_session",
            "category": "session",
            "tenant_id": tenant_id,
        },
        principal,
    )
    audit_answer = execute("audit", audit_payload, action="log")
    governance_answer = execute(
        "governance_gate",
        {"tenant_id": tenant_id, "action_type": "faculty_session", "target_id": reference},
        action="list_requests",
    )

    answers = {
        "knowledge": knowledge_answer,
        "memory": memory_answer,
        "audit": audit_answer,
        "governance_gate": governance_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    record = {
        "reference": reference,
        "status": domain.text(data.get("status") or "open"),
        "learner_email": learner,
        "track_id": domain.text(track.get("id")),
        "track_version": domain.text(track.get("file_version")),
        "week": week_number,
        "session_offset": domain.integer(data.get("session_offset")),
        "mode": mode,
        "term": int(term.get("number") or 0),
        "week_theme": domain.text(week.get("theme")),
        "message": message,
        "kind": composed["kind"],
        "turns": composed["turns"],
        "transcript": transcript,
        "deliverable_written": bool(composed["deliverable_written"]),
        "refused": composed["refused"],
        "faculty_sources": composed["source_week"],
        "corpus_hits": len((knowledge_answer or {}).get("results") or [])
        if isinstance(knowledge_answer, dict)
        else 0,
        "audit_row": {
            "principal_id": principal,
            "action_name": "faculty_session.%s" % mode,
            "resource_id": reference,
        },
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        deliverable_written=bool(composed["deliverable_written"]),
        refused=composed["refused"],
    )
