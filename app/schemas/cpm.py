"""Typed inputs and outputs for the CPM scheduling surface.

The sealed ``cpm_engine`` block reads these models by name
(``app.schemas.cpm``); they are the product-side contract for a critical-path
computation over the session schedule the enrolment handler expands.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Activity(BaseModel):
    """One scheduled activity. Durations are the unit the caller works in."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    duration: float = 0.0
    predecessors: List[str] = Field(default_factory=list)
    resources: Dict[str, float] = Field(default_factory=dict)


class WorkCalendar(BaseModel):
    """Which weekdays are working days (Monday == 0)."""

    model_config = ConfigDict(extra="allow")

    work_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class CPMInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    activities: List[Activity] = Field(default_factory=list)
    project_start: Optional[date] = None
    calendar: WorkCalendar = Field(default_factory=WorkCalendar)


class ActivityResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    duration: float = 0.0
    early_start: float = 0.0
    early_finish: float = 0.0
    late_start: float = 0.0
    late_finish: float = 0.0
    total_float: float = 0.0
    critical: bool = False
    start: Optional[date] = None
    finish: Optional[date] = None


class CPMOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_duration: float = 0.0
    project_finish: Optional[date] = None
    critical_path: List[str] = Field(default_factory=list)
    critical_percentage: float = 0.0
    near_critical: List[str] = Field(default_factory=list)
    results: List[ActivityResult] = Field(default_factory=list)


class HistogramBucket(BaseModel):
    model_config = ConfigDict(extra="allow")

    period: str
    start: Optional[date] = None
    end: Optional[date] = None
    demand: Dict[str, float] = Field(default_factory=dict)
    total: float = 0.0


class GanttBar(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    start: Optional[date] = None
    finish: Optional[date] = None
    duration: float = 0.0
    critical: bool = False
    total_float: float = 0.0


class ResourceHistogram(BaseModel):
    model_config = ConfigDict(extra="allow")

    period_unit: str = "week"
    buckets: List[HistogramBucket] = Field(default_factory=list)
    peak: Dict[str, float] = Field(default_factory=dict)


def model_dump(model: Any) -> Dict[str, Any]:
    """Small helper for callers that hold a plain mapping instead of a model."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return dict(model or {})
