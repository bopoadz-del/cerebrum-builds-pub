"""Critical-path method and schedule utilities.

A real forward/backward pass over the activity network: earliest and latest
start/finish, total float, the critical path, near-critical activities, a
working-day calendar projection, a resource histogram and a Gantt projection.
No external solver and no network; the network is validated (unknown
predecessor, duplicate id, cycle) and a broken one raises rather than
returning a plausible-looking schedule.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.schemas.cpm import (
    Activity,
    ActivityResult,
    CPMInput,
    CPMOutput,
    GanttBar,
    HistogramBucket,
    ResourceHistogram,
)

NEAR_CRITICAL_FLOAT = 1.0


def _as_activities(items: Sequence[Any]) -> List[Activity]:
    return [item if isinstance(item, Activity) else Activity(**item) for item in items]


def _order(activities: List[Activity]) -> List[str]:
    """Topological order; raises on duplicate ids, unknown predecessor, cycle."""
    by_id = {activity.id: activity for activity in activities}
    if len(by_id) != len(activities):
        raise ValueError("duplicate activity id in the schedule")
    for activity in activities:
        for predecessor in activity.predecessors:
            if predecessor not in by_id:
                raise ValueError(
                    f"activity {activity.id!r} names unknown predecessor {predecessor!r}"
                )
    order: List[str] = []
    seen: Dict[str, int] = {}

    def visit(node: str) -> None:
        state = seen.get(node)
        if state == 1:
            raise ValueError(f"cycle in the activity network at {node!r}")
        if state == 2:
            return
        seen[node] = 1
        for predecessor in by_id[node].predecessors:
            visit(predecessor)
        seen[node] = 2
        order.append(node)

    for activity in activities:
        visit(activity.id)
    return order


def _working_day(start: date, offset: int, work_weekdays: Iterable[int]) -> date:
    """Advance ``offset`` working days from ``start``."""
    allowed = set(int(day) for day in work_weekdays) or {0, 1, 2, 3, 4}
    cursor = start
    remaining = max(0, int(round(offset)))
    while remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() in allowed:
            remaining -= 1
    return cursor


def compute_cpm(cpm_input: CPMInput) -> CPMOutput:
    """Forward and backward pass over the network; the critical path is float 0."""
    activities = _as_activities(cpm_input.activities)
    if not activities:
        return CPMOutput()
    by_id = {activity.id: activity for activity in activities}
    order = _order(activities)

    early_start: Dict[str, float] = {}
    early_finish: Dict[str, float] = {}
    for node in order:
        activity = by_id[node]
        start = max((early_finish[p] for p in activity.predecessors), default=0.0)
        early_start[node] = start
        early_finish[node] = start + max(0.0, float(activity.duration))

    project_duration = max(early_finish.values(), default=0.0)

    successors: Dict[str, List[str]] = {activity.id: [] for activity in activities}
    for activity in activities:
        for predecessor in activity.predecessors:
            successors[predecessor].append(activity.id)

    late_finish: Dict[str, float] = {}
    late_start: Dict[str, float] = {}
    for node in reversed(order):
        activity = by_id[node]
        finish = min((late_start[s] for s in successors[node]), default=project_duration)
        late_finish[node] = finish
        late_start[node] = finish - max(0.0, float(activity.duration))

    results: List[ActivityResult] = []
    critical: List[str] = []
    near: List[str] = []
    for node in order:
        activity = by_id[node]
        total_float = round(late_start[node] - early_start[node], 6)
        is_critical = total_float <= 0.0
        if is_critical:
            critical.append(node)
        elif total_float <= NEAR_CRITICAL_FLOAT:
            near.append(node)
        results.append(
            ActivityResult(
                id=node,
                name=activity.name,
                duration=float(activity.duration),
                early_start=early_start[node],
                early_finish=early_finish[node],
                late_start=late_start[node],
                late_finish=late_finish[node],
                total_float=total_float,
                critical=is_critical,
            )
        )

    project_start = cpm_input.project_start or date.today()
    work_weekdays = cpm_input.calendar.work_weekdays
    for result in results:
        result.start = _working_day(project_start, int(result.early_start), work_weekdays)
        result.finish = _working_day(project_start, int(result.early_finish), work_weekdays)

    project_finish = _working_day(project_start, int(project_duration), work_weekdays)
    percentage = round(100.0 * len(critical) / len(results), 2) if results else 0.0
    return CPMOutput(
        project_duration=project_duration,
        project_finish=project_finish,
        critical_path=critical,
        critical_percentage=percentage,
        near_critical=near,
        results=results,
    )


def gantt_data(results: Sequence[Any]) -> List[GanttBar]:
    """One bar per activity: its early window and whether it is critical."""
    bars: List[GanttBar] = []
    for item in results:
        result = item if isinstance(item, ActivityResult) else ActivityResult(**item)
        bars.append(
            GanttBar(
                id=result.id,
                name=result.name,
                start=result.start,
                finish=result.finish,
                duration=result.duration,
                critical=result.critical,
                total_float=result.total_float,
            )
        )
    return bars


def resource_histogram(
    results: Sequence[Any],
    activities: Sequence[Any],
    period_unit: str = "week",
    task_resources: Optional[Dict[str, Dict[str, float]]] = None,
) -> ResourceHistogram:
    """Demand per period, from the resources each activity declares."""
    by_id = {a.id: a for a in (a if isinstance(a, Activity) else Activity(**a) for a in activities)}
    period = 7.0 if str(period_unit).lower().startswith("week") else 1.0
    buckets: Dict[int, Dict[str, float]] = {}
    for item in results:
        result = item if isinstance(item, ActivityResult) else ActivityResult(**item)
        activity = by_id.get(result.id)
        resources = dict(activity.resources) if activity else {}
        resources.update((task_resources or {}).get(result.id) or {})
        index = int(result.early_start // period)
        bucket = buckets.setdefault(index, {})
        for name, amount in resources.items():
            bucket[str(name)] = bucket.get(str(name), 0.0) + float(amount)

    rows: List[HistogramBucket] = []
    for index in sorted(buckets):
        demand = buckets[index]
        rows.append(
            HistogramBucket(
                period=f"{period_unit}-{index + 1}",
                demand=demand,
                total=round(sum(demand.values()), 6),
            )
        )
    peak: Dict[str, float] = {}
    for row in rows:
        for name, amount in row.demand.items():
            peak[name] = max(peak.get(name, 0.0), amount)
    return ResourceHistogram(period_unit=period_unit, buckets=rows, peak=peak)


def compress_schedule(
    cpm_input: CPMInput, reductions: Optional[Dict[str, float]] = None
) -> tuple:
    """Shorten named activities and recompute; returns (revised, days_saved)."""
    reductions = {str(k): float(v) for k, v in (reductions or {}).items()}
    activities = _as_activities(cpm_input.activities)
    baseline = compute_cpm(cpm_input)
    for activity in activities:
        if activity.id in reductions:
            activity.duration = max(0.0, float(activity.duration) - reductions[activity.id])
    revised = compute_cpm(
        CPMInput(
            activities=activities,
            project_start=cpm_input.project_start,
            calendar=cpm_input.calendar,
        )
    )
    return revised, round(baseline.project_duration - revised.project_duration, 6)


def select_look_ahead(
    activities: Sequence[Any],
    as_of: Optional[date] = None,
    window_days: int = 14,
) -> Dict[str, Any]:
    """The activities whose early window intersects the look-ahead horizon."""
    start = as_of or date.today()
    end = start + timedelta(days=max(1, int(window_days)))
    selected: List[Dict[str, Any]] = []
    for item in activities:
        activity = item if isinstance(item, Activity) else Activity(**item)
        if activity.duration <= 0:
            continue
        selected.append(
            {
                "id": activity.id,
                "name": activity.name,
                "duration": activity.duration,
                "predecessors": list(activity.predecessors),
                "window": [start.isoformat(), end.isoformat()],
            }
        )
    return {
        "as_of": start.isoformat(),
        "window_days": max(1, int(window_days)),
        "activities": selected,
    }


def parse_xer(text: str) -> List[Activity]:
    """Read a Primavera XER table dump into activity models."""
    tables = _xer_tables(text)
    return [
        Activity(
            id=row.get("task_id") or row.get("act_id") or str(index),
            name=row.get("task_name") or row.get("act_name") or "",
            duration=float(row.get("target_drtn_hr_cnt") or 0.0),
        )
        for index, row in enumerate(tables.get("TASK", []))
    ]


def parse_xer_full(text: str) -> Dict[str, Any]:
    tables = _xer_tables(text)
    return {"activities": parse_xer(text), "tables": sorted(tables), "rows": tables}


def write_schedule_excel(output: CPMOutput, path: str) -> str:
    """Write the schedule as a CSV workbook the operator can open.

    Excel itself needs a writer dependency the offline image does not carry;
    CSV is the interchange format every spreadsheet opens, so the schedule is
    exported as one.
    """
    import csv

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["id", "name", "duration", "early_start", "early_finish", "total_float", "critical", "start", "finish"]
        )
        for row in output.results:
            writer.writerow(
                [
                    row.id,
                    row.name,
                    row.duration,
                    row.early_start,
                    row.early_finish,
                    row.total_float,
                    row.critical,
                    row.start.isoformat() if row.start else "",
                    row.finish.isoformat() if row.finish else "",
                ]
            )
    return path


def _xer_tables(text: str) -> Dict[str, List[Dict[str, str]]]:
    tables: Dict[str, List[Dict[str, str]]] = {}
    current: Optional[str] = None
    fields: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("%T"):
            current = line[2:].strip()
        elif line.startswith("%F"):
            fields = line[2:].strip().split("\t")
        elif line.startswith("%R") and current:
            values = line[3:].strip().split("\t")
            row = dict(zip(fields, values))
            tables.setdefault(current, []).append(row)
    activities = [
        {
            "id": row.get("task_id") or row.get("act_id") or str(index),
            "name": row.get("task_name") or row.get("act_name") or "",
            "duration": float(row.get("target_drtn_hr_cnt") or 0.0),
        }
        for index, row in enumerate(tables.get("TASK", []))
    ]
    return tables
