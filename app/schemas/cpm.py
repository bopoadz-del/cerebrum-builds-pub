"""Schedule models the vendored cpm_engine reads (its declared host contract).

The block imports app.schemas.cpm and app.lib.pm_computations; these are
the platform-side types its port was written against.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Activity(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    duration: int = 0
    predecessors: List[str] = Field(default_factory=list)
    resources: Dict[str, Any] = Field(default_factory=dict)


class WorkCalendar(BaseModel):
    work_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class CPMInput(BaseModel):
    activities: List[Activity] = Field(default_factory=list)
    project_start: Optional[date] = None
    calendar: WorkCalendar = Field(default_factory=WorkCalendar)


class CPMResult(BaseModel):
    activity_id: str
    name: str = ""
    duration: int = 0
    early_start: int = 0
    early_finish: int = 0
    late_start: int = 0
    late_finish: int = 0
    total_float: int = 0
    critical: bool = False
    start: Optional[date] = None
    finish: Optional[date] = None


class CPMOutput(BaseModel):
    project_duration: int = 0
    project_finish: Optional[date] = None
    critical_path: List[str] = Field(default_factory=list)
    critical_percentage: float = 0.0
    near_critical: List[str] = Field(default_factory=list)
    results: List[CPMResult] = Field(default_factory=list)


class HistogramBar(BaseModel):
    period: str
    value: float = 0.0


class HistogramOutput(BaseModel):
    period_unit: str = "week"
    bars: List[HistogramBar] = Field(default_factory=list)


class GanttBar(BaseModel):
    activity_id: str
    start: int = 0
    finish: int = 0
    critical: bool = False
