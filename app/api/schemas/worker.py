from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.api.schemas.employee_profile import EmployeeProfile
from app.api.schemas.employee_settings import EmployeeSettings
from app.models.enums import UserStatus


class WorkerCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    password: str | None = None
    department_id: int | None = None
    job_id: int | None = None
    status: UserStatus = UserStatus.ACTIVE


class WorkerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    department_id: int | None = None
    job_id: int | None = None
    status: UserStatus | None = None


class Worker(BaseModel):
    id: int
    name: str
    email: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    job_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkerDetail(Worker):
    profile: EmployeeProfile | None = None
    settings: EmployeeSettings | None = None
