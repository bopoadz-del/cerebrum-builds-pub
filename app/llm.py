"""Faculty narration, composed from the week's own data.

This platform makes no provider call. Every faculty turn is built from the
week record the track file supplies -- its theme, concepts, readings, cases
and the track's rubric criteria -- plus the learner's message. Nothing is
carried over from another week and no programme text lives in this module:
change the track file and the faculty content changes with it.

The six kernel modes differ in what they do with that material:

* lecture    an exposition of the week's framework and sources
* brief      a short, decision-shaped brief
* socratic   questions only
* sparring   challenges that test the learner's reasoning -- and a refusal to
             write the learner's deliverable, whatever the request says
* oral_quiz  questions with answers withheld (they are released in examiner)
* examiner   a rubric-aligned examination of the learner's position
"""

from __future__ import annotations

from typing import Any, Dict, List

MODES = ("lecture", "brief", "socratic", "sparring", "oral_quiz", "examiner")

_WRITE_REQUEST_MARKERS = (
    "write my",
    "write the memo",
    "draft the memo",
    "do my",
    "write it for me",
    "draft it for me",
    "write my deliverable",
    "produce the deliverable",
    "write the deliverable",
)


class FacultyError(ValueError):
    """A session that cannot be composed from the week data supplied."""


def _list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _titles(value: Any) -> List[str]:
    out: List[str] = []
    for item in value or []:
        if isinstance(item, dict):
            out.append(str(item.get("title") or item.get("id") or "").strip())
        else:
            out.append(str(item).strip())
    return [title for title in out if title]


def _wants_deliverable(message: str) -> bool:
    text = str(message or "").lower()
    return any(marker in text for marker in _WRITE_REQUEST_MARKERS)


def compose(
    mode: str,
    week: Dict[str, Any],
    track: Dict[str, Any],
    message: str = "",
) -> Dict[str, Any]:
    """One faculty session turn, from the week data alone."""
    chosen = str(mode or "").strip().lower()
    if chosen not in MODES:
        raise FacultyError("unknown kernel mode %r; expected one of: %s" % (mode, ", ".join(MODES)))
    if not isinstance(week, dict) or not week:
        raise FacultyError("no week data was supplied: faculty content is built from the week record")

    theme = str(week.get("theme") or "").strip()
    if not theme:
        raise FacultyError("the week record has no theme: faculty content is built from the week record")
    concepts = _list(week.get("concepts"))
    readings = _titles(week.get("readings"))
    cases = _titles(week.get("cases"))
    rubrics = [
        str(item.get("label") or item.get("id") or "")
        for item in (track.get("rubric") or {}).get("criteria") or []
    ]
    references = readings + cases
    turns: List[str] = []
    kind = "lecture"

    if chosen == "lecture":
        turns.append("This week's framework: %s." % theme)
        if concepts:
            turns.append("Work through these ideas in order: %s." % "; ".join(concepts))
        if readings:
            turns.append("Read: %s." % "; ".join(readings))
        if cases:
            turns.append("You will meet: %s." % "; ".join(cases))
        turns.append(
            "Bring one decision from your own organisation that this framework would change, "
            "and be ready to defend the mechanism you used."
        )
        kind = "exposition"
    elif chosen == "brief":
        turns.append("Brief -- %s" % theme)
        turns.append("Position: the week turns on %s." % (concepts[0] if concepts else theme))
        if references:
            turns.append("Evidence to hand: %s." % "; ".join(references))
        turns.append("Ask to answer before the case session: what would have to be true for the opposite reading?")
        kind = "brief"
    elif chosen == "socratic":
        base = concepts or [theme]
        for concept in base[:3]:
            turns.append("How would you know that %s is the binding constraint, rather than a symptom?" % concept)
        if cases:
            turns.append("What would change your mind about %s?" % cases[0])
        kind = "questions"
    elif chosen == "sparring":
        if _wants_deliverable(message):
            return {
                "mode": chosen,
                "kind": "refusal",
                "turns": [
                    "I will not write your deliverable. That is the assessment, and writing it for you "
                    "would destroy the evidence it exists to produce."
                ],
                "refused": "sparring_does_not_write_deliverables",
                "deliverable_written": False,
                "source_week": {
                    "theme": theme,
                    "concepts": concepts,
                    "readings": readings,
                    "cases": cases,
                },
            }
        turns.append("Take the position that %s is being solved at the wrong level. Defend it." % theme)
        if concepts:
            turns.append("Your claim rests on %s -- what is the strongest counter-argument?" % concepts[0])
        turns.append("Name the evidence you do not have. I will press on that first.")
        kind = "challenge"
    elif chosen == "oral_quiz":
        questions = [
            "Define %s and give one failure mode it does not explain." % (concepts[0] if concepts else theme),
            "Which of this week's sources would you cite against your own recommendation, and why?",
            "State the decision rule you would apply on Monday, in one sentence.",
        ]
        turns.extend(questions)
        kind = "quiz"
    else:  # examiner
        turns.append("Examination -- %s" % theme)
        for criterion in (rubrics or ["the week's framework"]):
            turns.append("Assess against '%s': what is your claim, the evidence, and the limit of that evidence?" % criterion)
        if references:
            turns.append("You may rely only on sources you name; I will ask for the page.")
        kind = "examination"

    return {
        "mode": chosen,
        "kind": kind,
        "turns": turns,
        "refused": "",
        "deliverable_written": False,
        "source_week": {
            "theme": theme,
            "concepts": concepts,
            "readings": readings,
            "cases": cases,
        },
    }


def transcript_entry(role: str, text: str) -> Dict[str, Any]:
    return {"role": str(role), "text": str(text)}
