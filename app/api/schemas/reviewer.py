from pydantic import BaseModel
from typing import Any, Dict


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
    text: str


class ReviewerDescriptionResponse(BaseModel):
    gigachat_response: Dict[str, Any]
