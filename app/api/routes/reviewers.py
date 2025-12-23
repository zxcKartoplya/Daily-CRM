from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.reviewer import Reviewer, ReviewerCreate, ReviewerUpdate
from app.db.session import get_db
from app.models import Reviewer as ReviewerModel


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=List[Reviewer])
def list_reviewers(db: Session = Depends(get_db)) -> List[Reviewer]:
    return db.query(ReviewerModel).all()


@router.get("/{reviewer_id}", response_model=Reviewer)
def get_reviewer(reviewer_id: int, db: Session = Depends(get_db)) -> Reviewer:
    reviewer = db.query(ReviewerModel).get(reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")
    return reviewer


@router.post("", response_model=Reviewer, status_code=status.HTTP_201_CREATED)
def create_reviewer(payload: ReviewerCreate, db: Session = Depends(get_db)) -> Reviewer:
    reviewer = ReviewerModel(**payload.dict())
    db.add(reviewer)
    db.commit()
    db.refresh(reviewer)
    return reviewer


@router.put("/{reviewer_id}", response_model=Reviewer)
def update_reviewer(
    reviewer_id: int, payload: ReviewerUpdate, db: Session = Depends(get_db)
) -> Reviewer:
    reviewer = db.query(ReviewerModel).get(reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    for field, value in payload.dict().items():
        setattr(reviewer, field, value)

    db.commit()
    db.refresh(reviewer)
    return reviewer


@router.delete("/{reviewer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reviewer(reviewer_id: int, db: Session = Depends(get_db)) -> None:
    reviewer = db.query(ReviewerModel).get(reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    db.delete(reviewer)
    db.commit()


@router.post("/description", status_code=status.HTTP_204_NO_CONTENT)
def mama():
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")