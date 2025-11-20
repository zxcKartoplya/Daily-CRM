from pydantic import BaseModel


class JobBase(BaseModel):
    name: str
    department_id: int


class JobCreate(JobBase):
    pass


class JobUpdate(JobBase):
    pass


class JobInDBBase(JobBase):
    id: int

    class Config:
        orm_mode = True


class Job(JobInDBBase):
    pass

