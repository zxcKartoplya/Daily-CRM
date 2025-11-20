from datetime import date

from pydantic import BaseModel


class TaskBase(BaseModel):
    user_id: int
    date: date
    description: str
    metric_id: int | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskInDBBase(TaskBase):
    id: int

    class Config:
        orm_mode = True


class Task(TaskInDBBase):
    pass

