from pydantic import BaseModel
from typing import List


class Metric(BaseModel):
    value: int
    json_name: str
    display_name: str
    description: str


class ReviewerBase(BaseModel):
    name: str
    description: str
    metrics: List[Metric] | None = None


class ReviewerCreate(ReviewerBase):
    pass


class ReviewerUpdate(ReviewerBase):
    pass


class Reviewer(ReviewerBase):
    id: int

    class Config:
        from_attributes = True


class ReviewerJobInfo(BaseModel):
    id: int
    name: str
    department_id: int
    department_name: str


class ReviewerWithJobs(Reviewer):
    jobs: List[ReviewerJobInfo]


class ReviewerDescriptionRequest(BaseModel):
    name: str
    description: str

class ReviewerDescriptionData(BaseModel):
    name: str
    summary: str
    metrics: List[Metric]

class ReviewerDescriptionResponse(BaseModel):
    gigachat_response: ReviewerDescriptionData
