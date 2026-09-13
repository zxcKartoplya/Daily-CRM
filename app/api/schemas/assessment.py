from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class AssessmentMetric(BaseModel):
    json_name: str
    display_name: str
    weight: int | None = None
    score: float | None = None


class AssessmentRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _validate_period(self) -> "AssessmentRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to")
        return self


class Assessment(BaseModel):
    id: int
    worker_id: int
    worker_name: str
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    job_id: int | None = None
    job_name: str | None = None
    created_at: datetime
    created_by: int | None = None
    model: str
    period_from: date
    period_to: date
    feedback: str
    metrics_snapshot: list[AssessmentMetric] = []

    model_config = ConfigDict(from_attributes=True)
