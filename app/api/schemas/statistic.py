from datetime import date

from pydantic import BaseModel, ConfigDict


class StatisticBase(BaseModel):
    date: date
    user_id: int
    value: int


class StatisticCreate(StatisticBase):
    pass


class StatisticUpdate(StatisticBase):
    pass


class StatisticInDBBase(StatisticBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Statistic(StatisticInDBBase):
    pass
