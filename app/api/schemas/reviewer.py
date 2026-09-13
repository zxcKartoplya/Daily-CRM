from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)


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


class ReviewerUsageMonth(BaseModel):
    month: str
    count: int


class ReviewerUsageMetric(BaseModel):
    json_name: str
    display_name: str
    avg_score: float
    samples: int


class ReviewerUsage(BaseModel):
    reviewer_id: int
    assessments_count: int
    assessments_last_30_days: int
    last_assessment_at: datetime | None = None
    workers_evaluated: int
    jobs_count: int
    employees_covered: int
    by_month: List[ReviewerUsageMonth] = []
    avg_scores: List[ReviewerUsageMetric] = []
    score_max: int
