from pydantic import BaseModel


class MetricBase(BaseModel):
    name: str
    cost: int


class MetricCreate(MetricBase):
    pass


class MetricUpdate(MetricBase):
    pass


class MetricInDBBase(MetricBase):
    id: int

    class Config:
        orm_mode = True


class Metric(MetricInDBBase):
    pass

