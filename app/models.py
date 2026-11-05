"""The eight capability records this platform emits.

Each class declares the fields the route and handler accept (FIELDS), the
constraints the writer/tester probe reads (CONSTRAINTS), and the entity its
rows live in (ENTITY -- the capability id). ``id`` and ``action`` are
reserved by the platform and are never domain fields.

Only ``reference`` and ``status`` are required. Everything a capability can
infer (a track's default week, a learner's pinned version, the term a date
falls in) is optional and resolved by the handler from the data the customer
actually supplied -- a track file, a rubric, a calendar.

The track selector (``track_id``, ``track_yaml``, ``track_path``) is an
accepted request input, not a declared writable field: its valid values are
the customer's own track files, which this module cannot enumerate without
hardwiring their ids. A caller sends it; the handler resolves it and refuses
an unknown one with the offending field path.
"""

from __future__ import annotations

from typing import Any, Dict, List

STATUS_VALUES = ["open", "in_progress", "closed"]

KERNEL_MODES = ["lecture", "brief", "socratic", "sparring", "oral_quiz", "examiner"]

DEFENSE_KINDS = ["defense", "resit", "capstone", "verdict"]

DEFENSE_VERDICTS = ["pass", "fail", "accept", "revise"]

TRACK_OPERATIONS = ["validate", "upload", "diff", "pin"]


class RecordModel:
    """Dict-backed record with a declared contract."""

    ENTITY = ""
    FIELDS: List[str] = ["reference", "status"]
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }
    MONEY_FIELDS: tuple[str, ...] = ()

    reference: str
    status: str

    def __init__(self, **values: Any) -> None:
        self._values: Dict[str, Any] = {}
        for name in self.FIELDS:
            if name in values:
                self._values[name] = values[name]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RecordModel":
        return cls(**dict(payload or {}))

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self._values)
        out.setdefault("id", None)
        return out

    def get(self, name: str, default: Any = None) -> Any:
        return self._values.get(name, default)


class TrackLoader(RecordModel):
    ENTITY = "track_loader"
    FIELDS = [
        "reference",
        "status",
        "schema_version",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }

    reference: str
    status: str
    track_id: str
    track_yaml: str
    track_path: str
    schema_version: str


class EnrolmentAndCalendar(RecordModel):
    ENTITY = "enrolment_and_calendar"
    FIELDS = [
        "reference",
        "status",
        "learner_name",
        "learner_email",
        "start_date",
        "timezone",
        "track_version",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
    }

    reference: str
    status: str
    learner_name: str
    learner_email: str
    track_id: str
    start_date: str
    timezone: str
    track_version: str


class FacultySession(RecordModel):
    ENTITY = "faculty_session"
    FIELDS = [
        "reference",
        "status",
        "learner_email",
        "week",
        "session_offset",
        "mode",
        "message",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "mode": {"allowed_values": KERNEL_MODES},
        "week": {"min": 1},
    }

    reference: str
    status: str
    learner_email: str
    track_id: str
    week: int
    session_offset: int
    mode: str
    message: str


class MemoGrading(RecordModel):
    ENTITY = "memo_grading"
    FIELDS = [
        "reference",
        "status",
        "learner_email",
        "week",
        "submission",
        "rubric_version",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "week": {"min": 1},
    }

    reference: str
    status: str
    learner_email: str
    track_id: str
    week: int
    submission: str
    rubric_version: str


class GradebookAndTranscript(RecordModel):
    ENTITY = "gradebook_and_transcript"
    FIELDS = [
        "reference",
        "status",
        "learner_email",
        "term",
        "memos_score",
        "defenses_score",
        "capstone_score",
        "prior_average",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "memos_score": {"min": 0, "max": 100},
        "defenses_score": {"min": 0, "max": 100},
        "capstone_score": {"min": 0, "max": 100},
        "prior_average": {"min": 0, "max": 100},
    }

    reference: str
    status: str
    learner_email: str
    track_id: str
    term: int
    memos_score: float
    defenses_score: float
    capstone_score: float
    prior_average: float


class DefenseAndCapstone(RecordModel):
    ENTITY = "defense_and_capstone"
    FIELDS = [
        "reference",
        "status",
        "learner_email",
        "term",
        "kind",
        "scheduled_date",
        "verdict",
        "reviewer_email",
        "defense_minutes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "kind": {"allowed_values": DEFENSE_KINDS},
        "verdict": {"allowed_values": DEFENSE_VERDICTS},
    }

    reference: str
    status: str
    learner_email: str
    track_id: str
    term: int
    kind: str
    scheduled_date: str
    verdict: str
    reviewer_email: str
    defense_minutes: int


class TrackAdmin(RecordModel):
    ENTITY = "track_admin"
    FIELDS = [
        "reference",
        "status",
        "operation",
        "pinned_version",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "operation": {"allowed_values": TRACK_OPERATIONS},
    }

    reference: str
    status: str
    track_id: str
    track_yaml: str
    operation: str
    pinned_version: str


class ReadingAndCaseLibrary(RecordModel):
    ENTITY = "reading_and_case_library"
    FIELDS = [
        "reference",
        "status",
        "week",
        "case_id",
        "learner_email",
        "session_offset",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"required": True, "allowed_values": STATUS_VALUES},
        "week": {"min": 1},
    }

    reference: str
    status: str
    track_id: str
    week: int
    case_id: str
    learner_email: str
    session_offset: int


MODELS: Dict[str, Any] = {
    TrackLoader.ENTITY: TrackLoader,
    EnrolmentAndCalendar.ENTITY: EnrolmentAndCalendar,
    FacultySession.ENTITY: FacultySession,
    MemoGrading.ENTITY: MemoGrading,
    GradebookAndTranscript.ENTITY: GradebookAndTranscript,
    DefenseAndCapstone.ENTITY: DefenseAndCapstone,
    TrackAdmin.ENTITY: TrackAdmin,
    ReadingAndCaseLibrary.ENTITY: ReadingAndCaseLibrary,
}
