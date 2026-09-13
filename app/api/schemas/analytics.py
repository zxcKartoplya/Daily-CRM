from datetime import date, datetime

from pydantic import BaseModel


class EmployeeStatistics(BaseModel):
    user_id: int
    streak: int
    completion_rate: float | None = None
    open_chains_count: int
    blockers_count: int
    dropped_chains_count: int
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
