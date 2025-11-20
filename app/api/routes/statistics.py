from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.statistic import Statistic, StatisticCreate, StatisticUpdate
from app.db.session import get_db
from app.models import Statistic as StatisticModel


router = APIRouter()


@router.get("/", response_model=List[Statistic])
def list_statistics(db: Session = Depends(get_db)) -> List[Statistic]:
    return db.query(StatisticModel).all()


@router.get("/{statistic_id}", response_model=Statistic)
def get_statistic(statistic_id: int, db: Session = Depends(get_db)) -> Statistic:
    statistic = db.query(StatisticModel).get(statistic_id)
    if not statistic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statistic not found")
    return statistic


@router.post("/", response_model=Statistic, status_code=status.HTTP_201_CREATED)
def create_statistic(payload: StatisticCreate, db: Session = Depends(get_db)) -> Statistic:
    statistic = StatisticModel(**payload.dict())
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
    statistic = db.query(StatisticModel).get(statistic_id)
    if not statistic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statistic not found")

    for field, value in payload.dict().items():
        setattr(statistic, field, value)

    db.commit()
    db.refresh(statistic)
    return statistic


@router.delete("/{statistic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statistic(statistic_id: int, db: Session = Depends(get_db)) -> None:
    statistic = db.query(StatisticModel).get(statistic_id)
    if not statistic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statistic not found")

    db.delete(statistic)
    db.commit()

