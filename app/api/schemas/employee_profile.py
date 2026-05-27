from pydantic import BaseModel, ConfigDict


class EmployeeProfileBase(BaseModel):
    position: str | None = None
    avatar: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None


class EmployeeProfileUpdate(EmployeeProfileBase):
    pass


class EmployeeProfile(EmployeeProfileBase):
    user_id: int

    model_config = ConfigDict(from_attributes=True)
