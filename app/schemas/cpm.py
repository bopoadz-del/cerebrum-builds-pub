"""Schedule primitives the cpm_engine block computes over.

The block ships the algorithm contract, not the host models: these are the
platform's own declarations of an activity, a work calendar and a computed
schedule, in the shape the block's ``compute``/``gantt``/``histogram`` actions
read and write.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WorkCalendar(BaseModel):
    work_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    holidays: List[_dt.date] = Field(default_factory=list)

    def is_working(self, day: _dt.date) -> bool:
        return day.weekday() in self.work_weekdays and day not in self.holidays


class Activity(BaseModel):
    id: str
    name: str = ""
    duration: int = 0
    predecessors: List[str] = Field(default_factory=list)
    resources: Dict[str, float] = Field(default_factory=dict)
    wbs: str = ""

    @property
    def duration_days(self) -> int:
        return max(int(self.duration or 0), 0)


class CPMInput(BaseModel):
    activities: List[Activity]
    project_start: Optional[_dt.date] = None
    calendar: WorkCalendar = Field(default_factory=WorkCalendar)


class ActivityResult(BaseModel):
    id: str
    name: str = ""
    duration: int = 0
    early_start: int = 0
    early_finish: int = 0
    late_start: int = 0
    late_finish: int = 0
    total_float: int = 0
    free_float: int = 0
    critical: bool = False
    predecessors: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    finish_date: Optional[str] = None


class CPMOutput(BaseModel):
    project_duration: int
    project_finish: Optional[_dt.date]
    critical_path: List[str]
    critical_percentage: float
    near_critical: List[str]
    results: List[ActivityResult]


class HistogramBucket(BaseModel):
    period: str
    start: str
    end: str
    resources: Dict[str, float]


class HistogramOutput(BaseModel):
    period_unit: str
    buckets: List[HistogramBucket]
    totals: Dict[str, float]


class GanttBar(BaseModel):
    id: str
    name: str
    start: str
    finish: str
    duration: int
    critical: bool
    predecessors: List[str] = Field(default_factory=list)
