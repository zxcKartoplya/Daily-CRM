from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.daily_entry import ChainHistory, DailyEntry, DailyEntryWrite, DayView
from app.db.session import get_db
from app.models import User as UserModel
from app.services.daily_entries import chain_history, day_view, list_entries, submit_entry, upsert_entry

router = APIRouter()
chains_router = APIRouter()


@router.get("", response_model=List[DailyEntry])
def list_employee_entries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> List[DailyEntry]:
    return list_entries(db, current_user.id, date_from=date_from, date_to=date_to)


@router.get("/{day}", response_model=DayView)
def get_employee_day(
    day: date,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DayView:
    return day_view(db, current_user, day)


@router.put("/{day}", response_model=DailyEntry)
def save_employee_day(
    day: date,
    payload: DailyEntryWrite,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DailyEntry:
    entry = upsert_entry(db, current_user, day, payload)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{day}/submit", response_model=DailyEntry, status_code=status.HTTP_200_OK)
def submit_employee_day(
    day: date,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DailyEntry:
    entry = submit_entry(db, current_user, day)
    db.commit()
    db.refresh(entry)
    return entry


@chains_router.get("/{chain_id}", response_model=ChainHistory)
def get_employee_chain(
    chain_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> ChainHistory:
    return chain_history(db, current_user.id, str(chain_id))
