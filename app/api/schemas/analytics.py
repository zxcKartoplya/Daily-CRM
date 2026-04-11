from datetime import datetime

from pydantic import BaseModel


class EmployeeStatistics(BaseModel):
    user_id: int
    streak: int
    completion_rate: float
    average_self_rating: float | None = None
    blockers_count: int
    last_report_at: datetime | None = None


class DepartmentAnalytics(BaseModel):
    department_id: int
    department_name: str
    employees_count: int
    reports_count: int
    average_self_rating: float | None = None
    needs_help_count: int


class AnalyticsOverview(BaseModel):
    employees_count: int
    departments_count: int
    reports_count: int
    reports_today: int
    needs_help_count: int
    average_self_rating: float | None = None
    last_report_at: datetime | None = None
    completion_rate_last_30_days: float
