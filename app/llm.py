"""The platform's offline language paths: AI faculty and the separate grader.

Two roles, two prompts, two code paths -- and no network. The faculty chat runs
in one of six kernel modes; the grader never sees the faculty transcript, which
is what makes its score an independent judgement rather than a conversation
grading itself. Both are deterministic rule engines over the text a learner
supplies: the platform ships the real behaviour (mode routing, refusal to
draft, rubric scoring, provenance) and needs no external model to run offline.

Nothing here reads a credential or opens a socket.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

RUBRIC_VERSION = "rubric.v1"
GRADER_VERSION = "grader.v1"
FACULTY_VERSION = "faculty.v1"

KERNEL_MODES = ("lecture", "brief", "socratic", "sparring", "oral_quiz", "examiner")

#: session kind -> the kernel mode it runs in (the brief's mapping).
MODE_BY_SESSION = {
    "framework": "lecture",
    "case_prep": "brief",
    "case_class": "socratic",
    "lab": "sparring",
    "exam": "examiner",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|percent|bps|million|bn|k)?\b", re.IGNORECASE)
_EVIDENCE = ("per", "according to", "source", "data", "evidence", "study", "reported", "measured", "exhibit", "figure")
_COUNTER = ("however", "although", "risk", "counter", "limitation", "alternatively", "on the other hand", "downside")
_RECOMMENDATION = ("recommend", "should", "we will", "the decision is", "propose", "next step", "commit")


def mode_for(session_kind: str, requested: str = "") -> str:
    """The kernel mode a session runs in: requested mode, else the mapping."""
    mode = str(requested or "").strip().lower()
    if mode in KERNEL_MODES:
        return mode
    mapped = MODE_BY_SESSION.get(str(session_kind or "").strip().lower(), "lecture")
    return mapped if mapped in KERNEL_MODES else "lecture"


def _keywords(text: str, limit: int = 6) -> List[str]:
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "have", "will", "what",
        "when", "which", "would", "could", "should", "about", "into", "your", "does",
        "how", "why", "are", "was", "were", "been", "you", "our", "their", "them",
    }
    seen: List[str] = []
    for word in _WORD.findall((text or "").lower()):
        if len(word) < 4 or word in stop or word in seen:
            continue
        seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def _focus(question: str, session_kind: str, week: int) -> str:
    keywords = _keywords(question)
    if keywords:
        return " / ".join(keywords[:3])
    return f"{session_kind or 'session'} week {week}"


def faculty_reply(
    mode: str,
    question: str,
    session_kind: str = "",
    week: int = 1,
    track_key: str = "",
    context: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """One faculty turn in the requested kernel mode.

    Sparring REFUSES to draft the learner's deliverable: it answers with
    questions that force the learner to commit to a position first.
    """
    mode = mode if mode in KERNEL_MODES else "lecture"
    focus = _focus(question, session_kind, week)
    citations = [item for item in (context or []) if item][:3]
    base = {
        "mode": mode,
        "session_kind": session_kind,
        "week": week,
        "track_key": track_key,
        "focus": focus,
        "citations": citations,
        "faculty_version": FACULTY_VERSION,
    }

    if mode == "lecture":
        base.update(
            question=question,
            answer=(
                f"Lecture framework: {focus}. Three moves. "
                f"(1) Definition: state what {focus} is in one sentence an operator could act on. "
                f"(2) Mechanism: name the two levers that move it and the constraint that binds them. "
                f"(3) Executive implication: what decision changes this week if the mechanism holds."
            ),
            followups=[f"Which lever does your organisation control directly?", f"What evidence would falsify this in {focus}?"],
            refuses_draft=False,
        )
    elif mode == "brief":
        base.update(
            question=question,
            answer=(
                f"Executive brief on {focus}: situation -- one line. "
                f"Insight -- the non-obvious relationship you should test. "
                f"Action -- the smallest commitment that buys information this week."
            ),
            followups=["What is the decision deadline?", "Which number would change your mind?"],
            refuses_draft=False,
        )
    elif mode == "socratic":
        base.update(
            question=question,
            answer=(
                f"I will not answer for you. Three questions on {focus}: "
                f"What assumption is load-bearing? What would a sceptical board member ask? "
                f"Which of your two options survives a 20% worse input?"
            ),
            followups=["State your position in one sentence before we continue."],
            refuses_draft=True,
            refusal_reason="socratic mode asks, it does not conclude",
        )
    elif mode == "sparring":
        base.update(
            question=question,
            answer=(
                "I will not draft your deliverable -- that is yours to write. "
                f"Answer these instead, on {focus}: "
                f"Who is the decision-maker and what do they already believe? "
                f"What is the strongest objection you are avoiding? "
                f"What is the one sentence you want the reader to repeat afterwards?"
            ),
            followups=["Bring me your draft sentence; I will stress-test it."],
            refuses_draft=True,
            refusal_reason="sparring mode refuses to draft the learner's deliverable",
        )
    elif mode == "oral_quiz":
        base.update(
            question=question,
            answer=(
                f"Oral quiz on {focus}. Q1 (recall): define the term precisely. "
                f"Q2 (apply): give a case where it fails. "
                f"Q3 (judge): choose between two defensible positions and defend the choice in 30 seconds."
            ),
            followups=["Answer Q1 aloud before reading Q2."],
            refuses_draft=False,
        )
    else:  # examiner
        base.update(
            question=question,
            answer=(
                f"Examiner mode on {focus}. You have 90 seconds per question. "
                f"Q1: state the claim. Q2: name the evidence. Q3: name the strongest counter-case and answer it. "
                f"Q4: state the recommendation and its failure condition."
            ),
            followups=["A pass requires Q3 and Q4; a re-sit is scheduled otherwise."],
            refuses_draft=False,
        )
    return base


# --- the grader: a separate path that never sees the faculty transcript -----

CRITERIA: List[Tuple[str, str]] = [
    ("thesis", "Thesis and framing (0-20)"),
    ("evidence", "Evidence and data (0-20)"),
    ("analysis", "Analysis and mechanism (0-20)"),
    ("counterargument", "Counter-case and risk (0-20)"),
    ("recommendation", "Executive recommendation (0-20)"),
]

_RUBRIC_NOTES = {
    "thesis": "a single falsifiable claim in the opening",
    "evidence": "named sources, figures or exhibits",
    "analysis": "a mechanism, not a description",
    "counterargument": "the strongest objection, answered",
    "recommendation": "a decision with an owner and a date",
}


def _clamp(value: float, low: float = 0.0, high: float = 20.0) -> float:
    return float(max(low, min(high, value)))


def _score_criterion(name: str, text: str, words: List[str], numbers: List[str], sentences: List[str]) -> Tuple[float, str]:
    lower = text.lower()
    length = len(words)
    base = 4.0 + min(8.0, length / 60.0)
    if name == "thesis":
        first = sentences[0].lower() if sentences else ""
        score = base + (4.0 if any(verb in first for verb in ("this memo", "i argue", "we argue", "the claim", "recommend")) else 0.0)
        score += 2.0 if "because" in first or "therefore" in first else 0.0
        verdict = "thesis is stated early" if score >= 12 else "thesis is implied, not stated"
    elif name == "evidence":
        hits = sum(1 for marker in _EVIDENCE if marker in lower)
        score = base + min(8.0, 2.0 * hits + 1.5 * len(numbers))
        verdict = f"{hits} evidence marker(s), {len(numbers)} figure(s)" if hits or numbers else "no evidence marker found"
    elif name == "analysis":
        mechanism = sum(1 for word in ("because", "drives", "leads to", "therefore", "mechanism", "trade-off", "constraint") if word in lower)
        score = base + min(8.0, 1.8 * mechanism)
        verdict = f"{mechanism} causal link(s)" if mechanism else "describes rather than explains"
    elif name == "counterargument":
        hits = sum(1 for marker in _COUNTER if marker in lower)
        score = base * 0.7 + min(9.0, 3.0 * hits)
        verdict = f"{hits} counter-case marker(s)" if hits else "no counter-case considered"
    else:
        hits = sum(1 for marker in _RECOMMENDATION if marker in lower)
        score = base + min(8.0, 2.5 * hits)
        verdict = f"{hits} recommendation marker(s)" if hits else "no decision stated"
    return round(_clamp(score), 1), verdict


def grade_memo(
    memo_text: str,
    rubric_version: str = RUBRIC_VERSION,
    learner_id: str = "",
    pass_floor: float = 70.0,
    merit_floor: float = 80.0,
    distinction_floor: float = 90.0,
) -> Dict[str, Any]:
    """Score a submitted memo against the rubric -- independently of faculty.

    Returns five criterion scores (0-20), the formula-evaluated total, the
    band, one verdict line per criterion, and the provenance a registrar needs
    (kernel/grader version, rubric version, run id, input digest).
    """
    from app import formulas

    text = str(memo_text or "")
    words = _WORD.findall(text)
    numbers = _NUMBER.findall(text)
    sentences = [part for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]

    scores: Dict[str, float] = {}
    verdicts: List[Dict[str, Any]] = []
    for name, label in CRITERIA:
        score, verdict = _score_criterion(name, text, words, numbers, sentences)
        scores[name] = score
        verdicts.append({"criterion": name, "label": label, "score": score, "verdict": verdict})

    total_row = formulas.memo_total(scores[name] for name, _ in CRITERIA)
    total = float(total_row["value"])
    band = formulas.band(total, pass_floor=pass_floor, merit_floor=merit_floor, distinction_floor=distinction_floor)

    return {
        "grader": GRADER_VERSION,
        "rubric_version": rubric_version or RUBRIC_VERSION,
        "learner_id": learner_id,
        "run_id": "grade_" + uuid.uuid4().hex[:12],
        "memo_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "word_count": len(words),
        "criteria": [
            {"criterion": name, "label": label, "score": scores[name], "max_score": 20}
            for name, label in CRITERIA
        ],
        "verdict_lines": verdicts,
        "total": total,
        "total_expression": total_row["expression"],
        "band": band,
        "pass_floor": pass_floor,
        "resit_required": total < float(pass_floor),
        "rubric_notes": _RUBRIC_NOTES,
        "faculty_transcript_visible": False,
    }
