from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.api.schemas.employee_profile import EmployeeProfile
from app.api.schemas.employee_settings import EmployeeSettings
from app.models.enums import UserRole, UserStatus


class UserBase(BaseModel):
    name: str
    email: EmailStr | None = None
    role: UserRole = UserRole.EMPLOYEE
    department_id: int | None = None
    status: UserStatus = UserStatus.ACTIVE
    job_id: int | None = None


class UserCreate(UserBase):
    password: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: UserRole | None = None
    department_id: int | None = None
    status: UserStatus | None = None
    password: str | None = None
    job_id: int | None = None


class UserInDBBase(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class User(UserInDBBase):
    department_name: str | None = None


class UserDetail(User):
    profile: EmployeeProfile | None = None
    settings: EmployeeSettings | None = None
