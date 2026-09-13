from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.daily_entry import AdminDailyEntry
from app.db.session import get_db
from app.models import DailyEntry as DailyEntryModel
from app.models import User as UserModel


router = APIRouter()


@router.get("", response_model=List[AdminDailyEntry])
def list_admin_entries(
    user_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    day_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[AdminDailyEntry]:
    query = (
        db.query(DailyEntryModel)
        .options(
            joinedload(DailyEntryModel.user),
            joinedload(DailyEntryModel.department),
            joinedload(DailyEntryModel.items),
        )
        .order_by(DailyEntryModel.date.desc(), DailyEntryModel.id.desc())
    )
    if user_id is not None:
        query = query.filter(DailyEntryModel.user_id == user_id)
    if department_id is not None:
        query = query.filter(DailyEntryModel.department_id == department_id)
    if status_filter is not None:
        query = query.filter(DailyEntryModel.status == status_filter)
    if day_type is not None:
        query = query.filter(DailyEntryModel.day_type == day_type)
    if date_from is not None:
        query = query.filter(DailyEntryModel.date >= date_from)
    if date_to is not None:
        query = query.filter(DailyEntryModel.date <= date_to)
    return query.all()


@router.get("/{entry_id}", response_model=AdminDailyEntry)
def get_admin_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> AdminDailyEntry:
    entry = (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(DailyEntryModel.id == entry_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись дня не найдена")
    return entry
