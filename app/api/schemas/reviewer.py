from pydantic import BaseModel
from typing import Any, Dict, List


class ReviewerBase(BaseModel):
    name: str
    description: str


class ReviewerCreate(ReviewerBase):
    pass


class ReviewerUpdate(ReviewerBase):
    pass


class Reviewer(ReviewerBase):
    id: int

    class Config:
        from_attributes = True


class ReviewerDescriptionRequest(BaseModel):
    name: str
    description: str

class Metric(BaseModel):
    value: int
    json_name: str
    display_name: str
    description: str

class ReviewerDescriptionData(BaseModel):
    name: str
    summary: str
    metrics: List[Metric]

class ReviewerDescriptionResponse(BaseModel):
    gigachat_response: ReviewerDescriptionData
