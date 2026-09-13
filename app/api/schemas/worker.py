from datetime import date, datetime

from pydantic import BaseModel, EmailStr, ConfigDict

from app.api.schemas.assessment import AssessmentMetric
from app.api.schemas.employee_profile import EmployeeProfile
from app.api.schemas.employee_settings import EmployeeSettings
from app.models.enums import ScheduleType, UserStatus


class WorkerCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    password: str | None = None
    department_id: int | None = None
    job_id: int | None = None
    status: UserStatus = UserStatus.ACTIVE
    schedule_type: ScheduleType | None = None
    work_days: list[int] | None = None


class WorkerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    department_id: int | None = None
    job_id: int | None = None
    status: UserStatus | None = None
    schedule_type: ScheduleType | None = None
    work_days: list[int] | None = None


class Worker(BaseModel):
    id: int
    name: str
    email: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    job_id: int | None = None
    job_name: str | None = None
    status: str
    schedule_type: ScheduleType
    work_days: list[int] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkerDetail(Worker):
    profile: EmployeeProfile | None = None
    settings: EmployeeSettings | None = None


class WorkerAIFeedback(BaseModel):
    id: int | None = None
    worker_id: int
    worker_name: str
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    job_id: int | None = None
    job_name: str | None = None
    created_at: datetime | None = None
    created_by: int | None = None
    model: str | None = None
    period_from: date | None = None
    period_to: date | None = None
    feedback: str
    metrics_snapshot: list[AssessmentMetric] = []
