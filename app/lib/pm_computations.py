"""Critical-path computations for the vendored cpm_engine.

A deterministic forward/backward pass over the activity network: the
duration, early and late dates, total float and the critical path are
derived from the network, with working-day calendars applied for dates.
A circular network or an unknown predecessor fails loudly.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.schemas.cpm import (
    Activity,
    CPMInput,
    CPMOutput,
    CPMResult,
    GanttBar,
    HistogramBar,
    HistogramOutput,
)


def _topological_order(activities: List[Activity]) -> List[Activity]:
    by_id = {activity.id: activity for activity in activities}
    if len(by_id) != len(activities):
        raise ValueError("activity ids must be unique")
    for activity in activities:
        for predecessor in activity.predecessors:
            if predecessor not in by_id:
                raise ValueError(f"unknown predecessor {predecessor!r} on {activity.id!r}")
    ordered: List[Activity] = []
    seen: Dict[str, int] = {}

    def visit(activity: Activity) -> None:
        state = seen.get(activity.id, 0)
        if state == 1:
            raise ValueError("circular dependency in the activity network")
        if state == 2:
            return
        seen[activity.id] = 1
        for predecessor in activity.predecessors:
            visit(by_id[predecessor])
        seen[activity.id] = 2
        ordered.append(activity)

    for activity in activities:
        visit(activity)
    return ordered


def _add_workdays(start: date, days: int, work_weekdays: List[int]) -> date:
    current = start
    remaining = max(0, int(days))
    while remaining:
        current += timedelta(days=1)
        if current.weekday() in work_weekdays:
            remaining -= 1
    return current


def compute_cpm(cpm_input: CPMInput) -> CPMOutput:
    activities = list(cpm_input.activities)
    if not activities:
        raise ValueError("no activities provided")
    ordered = _topological_order(activities)
    duration = {activity.id: max(0, int(activity.duration)) for activity in activities}
    predecessors = {activity.id: list(activity.predecessors) for activity in activities}

    early_start: Dict[str, int] = {}
    early_finish: Dict[str, int] = {}
    for activity in ordered:
        start = max((early_finish[p] for p in predecessors[activity.id]), default=0)
        early_start[activity.id] = start
        early_finish[activity.id] = start + duration[activity.id]
    project_duration = max(early_finish.values(), default=0)

    successors: Dict[str, List[str]] = {activity.id: [] for activity in activities}
    for activity in activities:
        for predecessor in predecessors[activity.id]:
            successors[predecessor].append(activity.id)

    late_finish: Dict[str, int] = {}
    late_start: Dict[str, int] = {}
    for activity in reversed(ordered):
        finish = min((late_start[s] for s in successors[activity.id]), default=project_duration)
        late_finish[activity.id] = finish
        late_start[activity.id] = finish - duration[activity.id]

    work_weekdays = list(cpm_input.calendar.work_weekdays or [0, 1, 2, 3, 4])
    project_start = cpm_input.project_start
    results: List[CPMResult] = []
    critical_path: List[str] = []
    near_critical: List[str] = []
    for activity in ordered:
        total_float = late_start[activity.id] - early_start[activity.id]
        critical = total_float <= 0
        if critical:
            critical_path.append(activity.id)
        elif total_float <= 2:
            near_critical.append(activity.id)
        start_date = _add_workdays(project_start, early_start[activity.id], work_weekdays) if project_start else None
        finish_date = _add_workdays(project_start, early_finish[activity.id], work_weekdays) if project_start else None
        results.append(CPMResult(
            activity_id=activity.id,
            name=activity.name,
            duration=duration[activity.id],
            early_start=early_start[activity.id],
            early_finish=early_finish[activity.id],
            late_start=late_start[activity.id],
            late_finish=late_finish[activity.id],
            total_float=total_float,
            critical=critical,
            start=start_date,
            finish=finish_date,
        ))

    project_finish = (
        _add_workdays(project_start, project_duration, work_weekdays) if project_start else None
    )
    return CPMOutput(
        project_duration=project_duration,
        project_finish=project_finish,
        critical_path=critical_path,
        critical_percentage=round(100.0 * len(critical_path) / len(results), 2) if results else 0.0,
        near_critical=near_critical,
        results=results,
    )


def resource_histogram(results: List[Any], activities: List[Activity], *,
                       period_unit: str = "week",
                       task_resources: Optional[Dict[str, Any]] = None) -> HistogramOutput:
    per_period: Dict[str, float] = {}
    for activity in activities:
        load = sum(float(v) for v in (activity.resources or {}).values()
                   if isinstance(v, (int, float)))
        if not load:
            continue
        for week in range(int(activity.duration)):
            key = "week-" + str(week + 1)
            per_period[key] = per_period.get(key, 0.0) + load
    return HistogramOutput(
        period_unit=period_unit,
        bars=[HistogramBar(period=key, value=round(value, 3))
              for key, value in sorted(per_period.items())],
    )


def gantt_data(results: List[CPMResult]) -> List[GanttBar]:
    return [GanttBar(activity_id=r.activity_id, start=r.early_start,
                     finish=r.early_finish, critical=r.critical) for r in results]


def compress_schedule(cpm_input: CPMInput, reductions: Dict[str, int]) -> tuple[CPMOutput, int]:
    reduced: List[Activity] = []
    for activity in cpm_input.activities:
        cut = max(0, int(reductions.get(activity.id, 0)))
        reduced.append(Activity(**{**activity.model_dump(),
                                   "duration": max(0, activity.duration - cut)}))
    output = compute_cpm(CPMInput(activities=reduced, project_start=cpm_input.project_start,
                                  calendar=cpm_input.calendar))
    baseline = compute_cpm(cpm_input)
    return output, max(0, baseline.project_duration - output.project_duration)


def select_look_ahead(activities: List[Any], *, as_of: Optional[date] = None,
                      window_days: int = 21) -> List[Dict[str, Any]]:
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    rows: List[Dict[str, Any]] = []
    limit = as_of or date.today()
    for item in activities:
        raw = item if isinstance(item, dict) else getattr(item, "__dict__", {})
        start = raw.get("start") or raw.get("early_start") or 0
        try:
            offset = int(start)
        except (TypeError, ValueError):
            continue
        if 0 <= offset <= window_days:
            rows.append(dict(raw))
    return rows


def parse_xer(text: str) -> List[Activity]:
    if not str(text or "").strip():
        raise ValueError("empty .xer blob")
    raise ValueError("xer parsing is not part of this platform's schedule contract")


def parse_xer_full(text: str) -> Dict[str, Any]:
    if not str(text or "").strip():
        raise ValueError("empty .xer blob")
    raise ValueError("xer parsing is not part of this platform's schedule contract")


def write_schedule_excel(output: CPMOutput, path: Optional[str] = None) -> str:
    if not path:
        raise ValueError("an output path is required")
    raise ValueError("excel export is not part of this platform's schedule contract")
