"""Capability models: what each capability declares it accepts.

Every model carries the platform envelope -- ``reference`` identifies the
record a caller is talking about, ``status`` is the schema-enforced
vocabulary ``open | in_progress | closed`` -- plus the domain fields that
capability actually uses. The constraints here are the contract the route
enforces and the one the harness builds its probe payload from, so a field
is only declared when the capability really reads it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

STATUS_VALUES = ["open", "in_progress", "closed"]

SESSION_KINDS = ["framework", "case_prep", "case_class", "lab", "exam"]
KERNEL_MODES = ["lecture", "brief", "socratic", "sparring", "oral_quiz", "examiner"]
OPERATOR_STAGES = ["enrol", "today", "session", "submit", "gradebook"]


class EntityModel:
    """The shared envelope and the persistence identity of one capability."""

    CAPABILITY_ID: str = ""
    ENTITY: str = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    MONEY_FIELDS: tuple = ()
    QUANTITY_FIELDS: tuple = ()

    id: Optional[int] = None
    tenant_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __init__(self, **values: Any) -> None:
        self.id = values.pop("id", None)
        self.tenant_id = values.pop("tenant_id", None)
        self.created_at = values.pop("created_at", None)
        self.updated_at = values.pop("updated_at", None)
        for name in self.FIELDS:
            setattr(self, name, values.get(name))

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "EntityModel":
        return cls(**(data or {}))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "reference": getattr(self, "reference", None),
            "status": getattr(self, "status", None),
        }
        for name in self.FIELDS:
            if name in out:
                continue
            out[name] = getattr(self, name, None)
        out["tenant_id"] = self.tenant_id
        out["created_at"] = self.created_at
        return out

    @classmethod
    def sample(cls) -> Dict[str, Any]:
        """A valid instance of this model, built from its own contract."""
        from app.validation import sample_for_model

        return sample_for_model(cls)


def _envelope(extra: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {
        "reference": {"type": "str", "required": True, "max_length": 200},
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES), "required": False},
    }
    out.update(extra)
    return out


class TrackManagement(EntityModel):
    """Operator surface: upload, validate, version and diff 16-week tracks."""

    CAPABILITY_ID = "track_management"
    ENTITY = "track_management"
    FIELDS = [
        "reference",
        "track_key",
        "title",
        "track_version",
        "weeks",
        "yaml_text",
        "previous_yaml",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "track_key": {"type": "str", "max_length": 80},
            "title": {"type": "str", "max_length": 200},
            "track_version": {"type": "int", "min": 1},
            "weeks": {"type": "int", "min": 1, "max": 52},
            "yaml_text": {"type": "str", "max_length": 200000},
            "previous_yaml": {"type": "str", "max_length": 200000},
        }
    )

    reference: str = ""
    track_key: str = ""
    title: str = ""
    track_version: int = 1
    weeks: int = 16
    yaml_text: str = ""
    previous_yaml: str = ""
    status: str = "open"


class EnrolmentAndScheduling(EntityModel):
    """Enrol a learner and generate the 16 x 6 session schedule."""

    CAPABILITY_ID = "enrolment_and_scheduling"
    ENTITY = "enrolment_and_scheduling"
    FIELDS = [
        "reference",
        "learner_email",
        "track_key",
        "start_date",
        "timezone",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "learner_email": {"type": "str", "format": "email", "max_length": 254},
            "track_key": {"type": "str", "max_length": 80},
            "start_date": {"type": "str", "format": "date"},
            "timezone": {"type": "str", "max_length": 64},
        }
    )

    reference: str = ""
    learner_email: str = ""
    track_key: str = ""
    start_date: str = ""
    timezone: str = "UTC"
    status: str = "open"


class AiFacultySessions(EntityModel):
    """Per-session AI faculty chat in one of the six kernel modes."""

    CAPABILITY_ID = "ai_faculty_sessions"
    ENTITY = "ai_faculty_sessions"
    FIELDS = [
        "reference",
        "session_kind",
        "kernel_mode",
        "week",
        "learner_question",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "session_kind": {"type": "str", "allowed_values": list(SESSION_KINDS)},
            "kernel_mode": {"type": "str", "allowed_values": list(KERNEL_MODES)},
            "week": {"type": "int", "min": 1, "max": 16},
            "learner_question": {"type": "str", "max_length": 4000},
        }
    )

    reference: str = ""
    session_kind: str = ""
    kernel_mode: str = ""
    week: int = 1
    learner_question: str = ""
    status: str = "open"


class MemoGrading(EntityModel):
    """The separate AI grader: five criterion scores from the rubric."""

    CAPABILITY_ID = "memo_grading"
    ENTITY = "memo_grading"
    FIELDS = [
        "reference",
        "learner_id",
        "memo_text",
        "rubric_version",
        "word_count",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "learner_id": {"type": "str", "max_length": 120},
            "memo_text": {"type": "str", "max_length": 200000},
            "rubric_version": {"type": "str", "max_length": 40},
            "word_count": {"type": "int", "min": 0, "max": 100000},
        }
    )

    reference: str = ""
    learner_id: str = ""
    memo_text: str = ""
    rubric_version: str = ""
    word_count: int = 0
    status: str = "open"


class GradebookAndTranscript(EntityModel):
    """Weighted average (memos 60, defenses 20, capstone 20) and transcript."""

    CAPABILITY_ID = "gradebook_and_transcript"
    ENTITY = "gradebook_and_transcript"
    FIELDS = [
        "reference",
        "learner_id",
        "memos_score",
        "defenses_score",
        "capstone_score",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "learner_id": {"type": "str", "max_length": 120},
            "memos_score": {"type": "float", "min": 0, "max": 100},
            "defenses_score": {"type": "float", "min": 0, "max": 100},
            "capstone_score": {"type": "float", "min": 0, "max": 100},
        }
    )

    reference: str = ""
    learner_id: str = ""
    memos_score: float = 0.0
    defenses_score: float = 0.0
    capstone_score: float = 0.0
    status: str = "open"


class DefensesAndCapstone(EntityModel):
    """Term defense, capstone review and the graduation rule."""

    CAPABILITY_ID = "defenses_and_capstone"
    ENTITY = "defenses_and_capstone"
    FIELDS = [
        "reference",
        "learner_id",
        "defense_date",
        "capstone_title",
        "reviewer_email",
        "verdict_count",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "learner_id": {"type": "str", "max_length": 120},
            "defense_date": {"type": "str", "format": "date"},
            "capstone_title": {"type": "str", "max_length": 200},
            "reviewer_email": {"type": "str", "format": "email", "max_length": 254},
            "verdict_count": {"type": "int", "min": 0, "max": 5},
        }
    )

    reference: str = ""
    learner_id: str = ""
    defense_date: str = ""
    capstone_title: str = ""
    reviewer_email: str = ""
    verdict_count: int = 0
    status: str = "open"


class LibrarySurfaces(EntityModel):
    """Per-week readings and cases; outcomes revealed in the case class only."""

    CAPABILITY_ID = "library_surfaces"
    ENTITY = "library_surfaces"
    FIELDS = [
        "reference",
        "track_key",
        "week",
        "session_kind",
        "query",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "track_key": {"type": "str", "max_length": 80},
            "week": {"type": "int", "min": 1, "max": 16},
            "session_kind": {"type": "str", "allowed_values": list(SESSION_KINDS)},
            "query": {"type": "str", "max_length": 500},
        }
    )

    reference: str = ""
    track_key: str = ""
    week: int = 1
    session_kind: str = ""
    query: str = ""
    status: str = "open"


class CommandCenterAndChat(EntityModel):
    """Operator command centre and the enrol -> gradebook operational chat."""

    CAPABILITY_ID = "command_center_and_chat"
    ENTITY = "command_center_and_chat"
    FIELDS = [
        "reference",
        "stage",
        "message",
        "status",
    ]
    CONSTRAINTS = _envelope(
        {
            "stage": {"type": "str", "allowed_values": list(OPERATOR_STAGES)},
            "message": {"type": "str", "max_length": 4000},
        }
    )

    reference: str = ""
    stage: str = ""
    message: str = ""
    status: str = "open"


MODELS: Dict[str, Any] = {
    TrackManagement.CAPABILITY_ID: TrackManagement,
    EnrolmentAndScheduling.CAPABILITY_ID: EnrolmentAndScheduling,
    AiFacultySessions.CAPABILITY_ID: AiFacultySessions,
    MemoGrading.CAPABILITY_ID: MemoGrading,
    GradebookAndTranscript.CAPABILITY_ID: GradebookAndTranscript,
    DefensesAndCapstone.CAPABILITY_ID: DefensesAndCapstone,
    LibrarySurfaces.CAPABILITY_ID: LibrarySurfaces,
    CommandCenterAndChat.CAPABILITY_ID: CommandCenterAndChat,
}

CAPABILITY_IDS: List[str] = list(MODELS)


def model_for(capability_id: str):
    return MODELS.get(str(capability_id or ""))


def entity_for(capability_id: str) -> str:
    cls = model_for(capability_id)
    if cls is None:
        raise KeyError(f"unknown capability: {capability_id}")
    return cls.ENTITY or cls.CAPABILITY_ID.replace("-", "_")
