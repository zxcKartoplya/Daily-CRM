from pydantic import BaseModel


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
