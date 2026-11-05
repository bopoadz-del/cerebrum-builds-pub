"""Critical-path computation over the activity network.

Host implementation the cpm_engine block calls: forward and backward pass,
total and free float, the critical path, a rolled-up histogram, Gantt bars,
compression by reduction, and an XER task-table reader.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.schemas.cpm import (
    Activity,
    ActivityResult,
    CPMInput,
    CPMOutput,
    GanttBar,
    HistogramBucket,
    HistogramOutput,
)


def _network(activities: Sequence[Activity]) -> Dict[str, Activity]:
    by_id: Dict[str, Activity] = {}
    for activity in activities:
        if activity.id in by_id:
            raise ValueError(f"duplicate activity id: {activity.id}")
        by_id[activity.id] = activity
    for activity in by_id.values():
        for predecessor in activity.predecessors:
            if predecessor not in by_id:
                raise ValueError(
                    f"unknown predecessor {predecessor!r} for activity {activity.id!r}"
                )
    return by_id


def _topological_order(by_id: Dict[str, Activity]) -> List[str]:
    indegree = {key: len(set(activity.predecessors)) for key, activity in by_id.items()}
    successors: Dict[str, List[str]] = {key: [] for key in by_id}
    for key, activity in by_id.items():
        for predecessor in set(activity.predecessors):
            successors[predecessor].append(key)
    ready = sorted(key for key, degree in indegree.items() if degree == 0)
    order: List[str] = []
    while ready:
        key = ready.pop(0)
        order.append(key)
        for successor in successors[key]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    if len(order) != len(by_id):
        raise ValueError("circular dependency in the activity network")
    return order


def _add_working_days(start: _dt.date, days: int, calendar) -> _dt.date:
    remaining = max(int(days), 0)
    current = start
    while remaining > 0:
        current += _dt.timedelta(days=1)
        if calendar.is_working(current):
            remaining -= 1
    while not calendar.is_working(current):
        current += _dt.timedelta(days=1)
    return current


def compute_cpm(cpm_input: CPMInput) -> CPMOutput:
    activities = list(cpm_input.activities or [])
    if not activities:
        raise ValueError("no activities")
    by_id = _network(activities)
    order = _topological_order(by_id)

    early_start: Dict[str, int] = {}
    early_finish: Dict[str, int] = {}
    for key in order:
        activity = by_id[key]
        start = max((early_finish[p] for p in set(activity.predecessors)), default=0)
        early_start[key] = start
        early_finish[key] = start + activity.duration_days

    project_duration = max(early_finish.values()) if early_finish else 0
    late_finish: Dict[str, int] = {key: project_duration for key in by_id}
    late_start: Dict[str, int] = {}
    successors: Dict[str, List[str]] = {key: [] for key in by_id}
    for key, activity in by_id.items():
        for predecessor in set(activity.predecessors):
            successors[predecessor].append(key)
    for key in reversed(order):
        following = successors[key]
        finish = min((late_start[s] for s in following), default=project_duration)
        late_finish[key] = finish
        late_start[key] = finish - by_id[key].duration_days

    start_date = cpm_input.project_start or _dt.date.today()
    calendar = cpm_input.calendar
    results: List[ActivityResult] = []
    for key in order:
        activity = by_id[key]
        total_float = late_start[key] - early_start[key]
        following = successors[key]
        free_float = (
            min((early_start[s] for s in following), default=project_duration)
            - early_finish[key]
        )
        results.append(
            ActivityResult(
                id=activity.id,
                name=activity.name,
                duration=activity.duration_days,
                early_start=early_start[key],
                early_finish=early_finish[key],
                late_start=late_start[key],
                late_finish=late_finish[key],
                total_float=total_float,
                free_float=max(free_float, 0),
                critical=total_float <= 0,
                predecessors=list(activity.predecessors),
                start_date=_add_working_days(start_date, early_start[key], calendar).isoformat(),
                finish_date=_add_working_days(start_date, early_finish[key], calendar).isoformat(),
            )
        )

    critical_path = [row.id for row in results if row.critical]
    near_critical = [row.id for row in results if 0 < row.total_float <= 2]
    critical_percentage = (
        round(100.0 * len(critical_path) / len(results), 2) if results else 0.0
    )
    return CPMOutput(
        project_duration=project_duration,
        project_finish=_add_working_days(start_date, project_duration, calendar),
        critical_path=critical_path,
        critical_percentage=critical_percentage,
        near_critical=near_critical,
        results=results,
    )


def gantt_data(results: Iterable[ActivityResult]) -> List[GanttBar]:
    bars: List[GanttBar] = []
    for row in results:
        bars.append(
            GanttBar(
                id=row.id,
                name=row.name or row.id,
                start=row.start_date or "",
                finish=row.finish_date or "",
                duration=row.duration,
                critical=row.critical,
                predecessors=list(row.predecessors),
            )
        )
    return bars


def resource_histogram(
    results: Iterable[ActivityResult],
    activities: Sequence[Activity],
    period_unit: str = "week",
    task_resources: Optional[Dict[str, Dict[str, float]]] = None,
) -> HistogramOutput:
    unit = str(period_unit or "week").lower()
    span = 7 if unit == "week" else 1
    by_id = {activity.id: activity for activity in activities}
    totals: Dict[str, float] = {}
    buckets: Dict[int, Dict[str, float]] = {}
    for row in results:
        resources = dict(by_id.get(row.id).resources) if by_id.get(row.id) else {}
        if task_resources:
            resources.update(task_resources.get(row.id) or {})
        first = row.early_start // span
        last = max(first, (row.early_finish - 1) // span)
        for bucket in range(first, last + 1):
            for name, quantity in resources.items():
                buckets.setdefault(bucket, {})
                buckets[bucket][name] = buckets[bucket].get(name, 0.0) + float(quantity)
                totals[name] = totals.get(name, 0.0) + float(quantity)
    base = _dt.date(2026, 1, 1)
    out: List[HistogramBucket] = []
    for bucket in sorted(buckets):
        start = base + _dt.timedelta(days=bucket * span)
        out.append(
            HistogramBucket(
                period=f"{unit}-{bucket + 1}",
                start=start.isoformat(),
                end=(start + _dt.timedelta(days=span - 1)).isoformat(),
                resources=buckets[bucket],
            )
        )
    return HistogramOutput(period_unit=unit, buckets=out, totals=totals)


def compress_schedule(cpm_input: CPMInput, reductions: Dict[str, int]) -> Tuple[CPMOutput, int]:
    by_id = {activity.id: activity for activity in cpm_input.activities}
    for key in reductions:
        if key not in by_id:
            raise ValueError(f"unknown activity id: {key}")
    baseline = compute_cpm(cpm_input).project_duration
    revised = []
    for activity in cpm_input.activities:
        reduce_by = int(reductions.get(activity.id, 0) or 0)
        revised.append(
            activity.model_copy(
                update={"duration": max(activity.duration_days - max(reduce_by, 0), 0)}
            )
        )
    after = compute_cpm(
        CPMInput(
            activities=revised,
            project_start=cpm_input.project_start,
            calendar=cpm_input.calendar,
        )
    )
    return after, baseline - after.project_duration


def select_look_ahead(
    activities: Sequence[Dict],
    as_of: Optional[_dt.date] = None,
    window_days: int = 21,
) -> Dict:
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    today = as_of or _dt.date.today()
    horizon = today + _dt.timedelta(days=int(window_days))
    due = []
    for activity in activities:
        raw = activity.get("start") or activity.get("early_start_date") or activity.get("start_date")
        if not raw:
            continue
        try:
            start = _dt.date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if today <= start <= horizon:
            due.append({**activity, "start": start.isoformat()})
    return {
        "as_of": today.isoformat(),
        "window_days": int(window_days),
        "horizon": horizon.isoformat(),
        "activities": due,
        "count": len(due),
    }


def parse_xer(text: str) -> List[Activity]:
    """Read the TASK table of a Primavera XER export."""
    tasks: List[Dict[str, str]] = []
    predecessors: List[Tuple[str, str]] = []
    table = ""
    for raw in str(text or "").splitlines():
        line = raw.rstrip("\n")
        if line.startswith("%T"):
            table = line.split("\t")[1] if "\t" in line else ""
            if table == "TASK":
                tasks.append({})
            continue
        if not line or line.startswith("%"):
            continue
        parts = line.split("\t")
        if table == "TASK" and tasks:
            row = tasks[-1]
            if len(parts) > 4:
                row.setdefault("id", parts[1])
                row.setdefault("name", parts[4] if len(parts) > 4 else "")
                row.setdefault("duration", parts[9] if len(parts) > 9 else "0")
        elif table == "TASKPRED" and len(parts) > 5:
            predecessors.append((parts[4], parts[5]))
    if not tasks:
        raise ValueError("the .xer text carries no TASK table")
    links: Dict[str, List[str]] = {}
    for task, predecessor in predecessors:
        links.setdefault(task, []).append(predecessor)
    out: List[Activity] = []
    for row in tasks:
        identifier = str(row.get("id") or "").strip()
        if not identifier:
            continue
        try:
            duration = int(float(row.get("duration") or 0))
        except ValueError:
            duration = 0
        out.append(
            Activity(
                id=identifier,
                name=str(row.get("name") or ""),
                duration=duration,
                predecessors=links.get(identifier, []),
            )
        )
    return out


def parse_xer_full(text: str) -> Dict:
    activities = parse_xer(text)
    return {
        "activities": activities,
        "count": len(activities),
        "source": "xer",
    }


def write_schedule_excel(output: CPMOutput, path: str) -> str:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Schedule"
    sheet.append(
        [
            "id",
            "name",
            "duration",
            "early_start",
            "early_finish",
            "late_start",
            "late_finish",
            "total_float",
            "critical",
            "start_date",
            "finish_date",
        ]
    )
    for row in output.results:
        sheet.append(
            [
                row.id,
                row.name,
                row.duration,
                row.early_start,
                row.early_finish,
                row.late_start,
                row.late_finish,
                row.total_float,
                row.critical,
                row.start_date,
                row.finish_date,
            ]
        )
    workbook.save(str(path))
    return str(path)
