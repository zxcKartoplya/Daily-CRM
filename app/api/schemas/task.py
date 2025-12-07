from datetime import date

from pydantic import BaseModel


class TaskBase(BaseModel):
    user_id: int
    date: date
    description: str


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskInDBBase(TaskBase):
    id: int

    class Config:
        from_attributes = True


class Task(TaskInDBBase):
    pass
