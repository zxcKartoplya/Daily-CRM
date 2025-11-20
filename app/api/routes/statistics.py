from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.statistic import Statistic, StatisticCreate, StatisticUpdate
from app.db.session import get_db
from app.models import (
    Statistic as StatisticModel,
    User as UserModel,
    Job as JobModel,
    Department as DepartmentModel,
    Admin as AdminModel,
)


router = APIRouter()


def _ensure_user_access(user: UserModel | None, current_admin: AdminModel) -> UserModel:
    if not user or user.job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _ensure_statistic_access(statistic: StatisticModel | None, current_admin: AdminModel) -> StatisticModel:
    if not statistic or statistic.user.job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statistic not found")
    return statistic


@router.get("/", response_model=List[Statistic])
def list_statistics(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Statistic]:
    return (
        db.query(StatisticModel)
        .join(StatisticModel.user)
        .join(UserModel.job)
        .join(JobModel.department)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .all()
    )


@router.get("/{statistic_id}", response_model=Statistic)
def get_statistic(
    statistic_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Statistic:
    statistic = db.query(StatisticModel).get(statistic_id)
    return _ensure_statistic_access(statistic, current_admin)


@router.post("/", response_model=Statistic, status_code=status.HTTP_201_CREATED)
def create_statistic(
    payload: StatisticCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Statistic:
    user = db.query(UserModel).get(payload.user_id)
    _ensure_user_access(user, current_admin)

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
    current_admin: AdminModel = Depends(require_admin),
) -> Statistic:
    statistic = db.query(StatisticModel).get(statistic_id)
    statistic = _ensure_statistic_access(statistic, current_admin)

    if payload.user_id != statistic.user_id:
        user = db.query(UserModel).get(payload.user_id)
        _ensure_user_access(user, current_admin)

    for field, value in payload.dict().items():
        setattr(statistic, field, value)

    db.commit()
    db.refresh(statistic)
    return statistic


@router.delete("/{statistic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statistic(
    statistic_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> None:
    statistic = db.query(StatisticModel).get(statistic_id)
    statistic = _ensure_statistic_access(statistic, current_admin)

    db.delete(statistic)
    db.commit()

