from datetime import date

from pydantic import BaseModel


class StatisticBase(BaseModel):
    date: date
    user_id: int
    metric_id: int
    value: int


class StatisticCreate(StatisticBase):
    pass


class StatisticUpdate(StatisticBase):
    pass


class StatisticInDBBase(StatisticBase):
    id: int

    class Config:
        orm_mode = True


class Statistic(StatisticInDBBase):
    pass

