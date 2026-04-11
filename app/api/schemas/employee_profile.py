from pydantic import BaseModel


class EmployeeProfileBase(BaseModel):
    position: str | None = None
    avatar: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None


class EmployeeProfileUpdate(EmployeeProfileBase):
    pass


class EmployeeProfile(EmployeeProfileBase):
    user_id: int

    class Config:
        from_attributes = True
