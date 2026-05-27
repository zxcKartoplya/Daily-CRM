from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.statistic import Statistic, StatisticCreate, StatisticUpdate
from app.db.session import get_db
from app.models import Statistic as StatisticModel
from app.models import User as UserModel


router = APIRouter(dependencies=[Depends(require_admin_user)])


def _get_statistic_or_404(db: Session, statistic_id: int) -> StatisticModel:
    statistic = db.get(StatisticModel, statistic_id)
    if not statistic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statistic not found")
    return statistic


def _ensure_worker_exists(db: Session, user_id: int) -> None:
    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")


@router.get("", response_model=List[Statistic])
def list_statistics(
    user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Statistic]:
    query = db.query(StatisticModel).order_by(StatisticModel.date.desc())
    if user_id is not None:
        query = query.filter(StatisticModel.user_id == user_id)
    return query.all()


@router.get("/{statistic_id}", response_model=Statistic)
def get_statistic(
    statistic_id: int,
    db: Session = Depends(get_db),
) -> Statistic:
    return _get_statistic_or_404(db, statistic_id)


@router.post("", response_model=Statistic, status_code=status.HTTP_201_CREATED)
def create_statistic(
    payload: StatisticCreate,
    db: Session = Depends(get_db),
) -> Statistic:
    _ensure_worker_exists(db, payload.user_id)
    statistic = StatisticModel(**payload.model_dump())
    db.add(statistic)
    db.commit()
    db.refresh(statistic)
    return statistic


@router.put("/{statistic_id}", response_model=Statistic)
def update_statistic(
    statistic_id: int,
    payload: StatisticUpdate,
    db: Session = Depends(get_db),
) -> Statistic:
    statistic = _get_statistic_or_404(db, statistic_id)
    if payload.user_id != statistic.user_id:
        _ensure_worker_exists(db, payload.user_id)
    for field, value in payload.model_dump().items():
        setattr(statistic, field, value)
    db.commit()
    db.refresh(statistic)
    return statistic


@router.delete("/{statistic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statistic(
    statistic_id: int,
    db: Session = Depends(get_db),
) -> None:
    statistic = _get_statistic_or_404(db, statistic_id)
    db.delete(statistic)
    db.commit()
