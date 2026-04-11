from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate
from app.db.session import get_db
from app.models import DailyReport as DailyReportModel
from app.models import User as UserModel
from app.services.daily_reports import create_daily_report, update_daily_report


router = APIRouter()


def _get_owned_report(db: Session, user_id: int, report_id: int) -> DailyReportModel:
    report = db.get(DailyReportModel, report_id)
    if not report or report.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily report not found")
    return report


@router.get("", response_model=List[DailyReport])
def list_employee_daily_reports(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> List[DailyReport]:
    query = (
        db.query(DailyReportModel)
        .filter(DailyReportModel.user_id == current_user.id)
        .order_by(DailyReportModel.report_date.desc())
    )
    if date_from is not None:
        query = query.filter(DailyReportModel.report_date >= date_from)
    if date_to is not None:
        query = query.filter(DailyReportModel.report_date <= date_to)
    return query.all()


@router.get("/{report_id}", response_model=DailyReport)
def get_employee_daily_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DailyReport:
    return _get_owned_report(db, current_user.id, report_id)


@router.post("", response_model=DailyReport, status_code=status.HTTP_201_CREATED)
def create_employee_daily_report(
    payload: DailyReportCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DailyReport:
    report = create_daily_report(db, user=current_user, payload=payload)
    db.commit()
    db.refresh(report)
    return report


@router.put("/{report_id}", response_model=DailyReport)
def update_employee_daily_report(
    report_id: int,
    payload: DailyReportUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> DailyReport:
    report = _get_owned_report(db, current_user.id, report_id)

    if payload.report_date and payload.report_date != report.report_date:
        duplicate = (
            db.query(DailyReportModel)
            .filter(
                DailyReportModel.user_id == current_user.id,
                DailyReportModel.report_date == payload.report_date,
                DailyReportModel.id != report.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily report for this date already exists",
            )

    report = update_daily_report(report, payload, user=current_user)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_daily_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> None:
    report = _get_owned_report(db, current_user.id, report_id)
    db.delete(report)
    db.commit()
