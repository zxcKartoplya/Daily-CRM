from pydantic import BaseModel


class JobBase(BaseModel):
    name: str
    department_id: int
    reviewer_id: int | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(JobBase):
    pass


class JobInDBBase(JobBase):
    id: int

    class Config:
        from_attributes = True


class Job(JobInDBBase):
    pass
