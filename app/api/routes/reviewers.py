from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.reviewer import (
    Reviewer,
    ReviewerCreate,
    ReviewerDescriptionRequest,
    ReviewerDescriptionResponse,
    ReviewerUpdate,
)
from app.db.session import get_db
from app.models import Reviewer as ReviewerModel
from app.services.gigachat import GigaChatClient


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


@router.post("/description", response_model=ReviewerDescriptionResponse)
def generate_description(payload: ReviewerDescriptionRequest) -> ReviewerDescriptionResponse:
    try:
        client = GigaChatClient()
        response = client.chat(payload.text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = {
            "status_code": exc.response.status_code,
            "message": "GigaChat request failed",
        }
        try:
            detail = exc.response.json()
        except ValueError:
            if exc.response.text:
                detail = {
                    "status_code": exc.response.status_code,
                    "message": exc.response.text,
                }
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GigaChat is unavailable: {exc}",
        ) from exc
    return ReviewerDescriptionResponse(gigachat_response=response)


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
