from typing import List
import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/description", response_model=ReviewerDescriptionResponse)
def generate_description(payload: ReviewerDescriptionRequest) -> ReviewerDescriptionResponse:
    client = GigaChatClient()
    base_prompt = (
        # Метрика: значение 1-10, json_название (id поля), имя для пользователя, короткое описание что отслеживает
        "Сформируй структурированное описание оценщика по короткому описанию. "
        "Ответ верни строго в JSON без markdown и без пояснений. Количество metrics должно быть от 4 и более. "
        "Поле value должно быть числом от 1 до 10. (оно отображает ценность и приоритетность метрики, значит чем больше значение value тем ценне метрика)"
        "Структура: {"
        "\"name\": string, "
        "\"summary\": string, "
        "\"what_is_evaluated\": [string], "
        "\"metrics\": ["
        "{"
        "\"value\": number, "
        "\"json_name\": string, "
        "\"display_name\": string, "
        "\"description\": string"
        "}"
        "],"
        "}."
    )
    prompt = f"{base_prompt} Название оценщика: {payload.name}. Короткое описание оценщика: {payload.description}."
    response = client.chat(prompt)
    content = response["choices"][0]["message"]["content"]
    cleaned = re.sub(r"^```json\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Invalid JSON from GigaChat: {exc}") from exc
    return ReviewerDescriptionResponse(gigachat_response=data)
