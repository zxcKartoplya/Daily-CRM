from pydantic import BaseModel, ConfigDict

from app.models.enums import ScheduleType


class JobBase(BaseModel):
    name: str
    description: str | None = None
    department_id: int
    reviewer_id: int
    schedule_type: ScheduleType = ScheduleType.WEEKLY
    work_days: list[int] | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(JobBase):
    pass


class JobInDBBase(JobBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Job(JobInDBBase):
    department_name: str | None = None
    reviewer_name: str | None = None
