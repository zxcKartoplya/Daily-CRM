from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import DayState


class WorkerStatistics(BaseModel):
    user_id: int
    period_from: date
    period_to: date
    working_days: int
    submitted_count: int
    draft_count: int
    missing_count: int
    off_count: int
    completion_rate: float | None = None
    streak: int
    longest_streak: int
    open_chains_count: int
    blockers_count: int
    dropped_chains_count: int
    done_items_count: int
    avg_items_per_day: float
    last_entry_at: datetime | None = None


class DepartmentAnalytics(BaseModel):
    department_id: int
    department_name: str
    employees_count: int
    entries_count: int
    open_chains_count: int
    blocked_items_count: int


class AnalyticsOverview(BaseModel):
    employees_count: int
    departments_count: int
    entries_count: int
    entries_today: int
    open_chains_count: int
    blocked_items_last_30_days: int
    last_entry_at: datetime | None = None
    completion_rate_last_30_days: float | None = None


class AnalyticsTimeseriesPoint(BaseModel):
    date: date
    working_employees: int
    submitted: int
    draft: int
    missing: int
    off: int
    completion_rate: float | None = None


class TodayState(BaseModel):
    user_id: int
    user_name: str
    department_id: int | None = None
    department_name: str | None = None
    job_name: str | None = None
    state: DayState
    entry_id: int | None = None
    submitted_at: datetime | None = None
