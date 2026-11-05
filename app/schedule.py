"""The fixed session template and the calendar it generates.

The template is a platform rule, not programme content: six sessions per
week on day offsets 0, 1, 2, 4, 5, 6 -- framework (90 min), case preparation
(60), case class (120), lab (90), lab (90), exam (60). It is the same for
every track, which is why it is not in the track file. What a session is
*about* comes from the week record; what a session *is* comes from here.

The calendar is generated in the learner's timezone, so the offset 3 rest day
is a local day and a DST transition cannot silently drop a session.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SESSION_TEMPLATE: List[Dict[str, Any]] = [
    {"day_offset": 0, "kind": "framework", "minutes": 90},
    {"day_offset": 1, "kind": "case_prep", "minutes": 60},
    {"day_offset": 2, "kind": "case_class", "minutes": 120},
    {"day_offset": 4, "kind": "lab", "minutes": 90},
    {"day_offset": 5, "kind": "lab", "minutes": 90},
    {"day_offset": 6, "kind": "exam", "minutes": 60},
]

DEFAULT_LENGTH_WEEKS = 16
DEFAULT_SESSION_START = "09:00"


class ScheduleError(ValueError):
    """A calendar that cannot be generated from the supplied values."""


def session_start_time() -> time:
    raw = (os.getenv("PLATFORM_SESSION_START") or DEFAULT_SESSION_START).strip()
    try:
        hour, minute = raw.split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        raise ScheduleError("PLATFORM_SESSION_START must be HH:MM, not %r" % raw)


def zone(name: str) -> ZoneInfo:
    raw = str(name or "").strip()
    if not raw:
        raise ScheduleError("a timezone is required (an IANA name such as a city/region)")
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        raise ScheduleError("unknown IANA timezone %r" % raw)


def parse_start(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    raise ScheduleError("start_date must be YYYY-MM-DD, not %r" % raw)


def generate(
    start_date: Any,
    timezone_name: str,
    length_weeks: int = DEFAULT_LENGTH_WEEKS,
) -> List[Dict[str, Any]]:
    """The full calendar: ``length_weeks`` x 6 sessions, starting on day 0."""
    start = parse_start(start_date)
    tz = zone(timezone_name)
    weeks = max(1, int(length_weeks or DEFAULT_LENGTH_WEEKS))
    begin = session_start_time()
    sessions: List[Dict[str, Any]] = []
    for week in range(1, weeks + 1):
        week_start = start + timedelta(days=(week - 1) * 7)
        for index, template in enumerate(SESSION_TEMPLATE):
            day = week_start + timedelta(days=int(template["day_offset"]))
            starts = datetime.combine(day, begin, tzinfo=tz)
            ends = starts + timedelta(minutes=int(template["minutes"]))
            sessions.append(
                {
                    "week": week,
                    "session_index": index + 1,
                    "day_offset": int(template["day_offset"]),
                    "kind": template["kind"],
                    "minutes": int(template["minutes"]),
                    "local_date": day.isoformat(),
                    "starts_at": starts.isoformat(),
                    "ends_at": ends.isoformat(),
                    "timezone": str(timezone_name),
                }
            )
    return sessions


def term_for_week(terms: List[Dict[str, Any]], week_number: int) -> Optional[Dict[str, Any]]:
    for term in terms or []:
        numbers = [int(week.get("number") or 0) for week in term.get("weeks") or []]
        if int(week_number) in numbers:
            return term
    return None


def term_last_day(sessions: List[Dict[str, Any]], term_number: int) -> Optional[str]:
    """The local date of the last session belonging to a term.

    The caller passes the sessions of that term (the calendar slice), so a
    term defense always lands on the term's own last day -- never a date
    computed from an assumption about how many weeks a term has.
    """
    dates = [entry.get("local_date") for entry in sessions if entry.get("term") == term_number]
    return max(dates) if dates else None


def outline(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Session counts by kind and the set of day offsets actually used."""
    counts: Dict[str, int] = {}
    for entry in sessions:
        kind = str(entry.get("kind"))
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "sessions": len(sessions),
        "by_kind": counts,
        "day_offsets": sorted({int(entry.get("day_offset", -1)) for entry in sessions}),
        "first_session": sessions[0] if sessions else None,
        "last_session": sessions[-1] if sessions else None,
    }
