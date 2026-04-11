from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.daily_report import DailyReport
from app.db.session import get_db
from app.models import DailyReport as DailyReportModel
from app.models import User as UserModel


router = APIRouter()


@router.get("", response_model=List[DailyReport])
def list_admin_reports(
    user_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    needs_help: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[DailyReport]:
    query = (
        db.query(DailyReportModel)
        .options(joinedload(DailyReportModel.user), joinedload(DailyReportModel.department))
        .order_by(DailyReportModel.report_date.desc(), DailyReportModel.submitted_at.desc())
    )
    if user_id is not None:
        query = query.filter(DailyReportModel.user_id == user_id)
    if department_id is not None:
        query = query.filter(DailyReportModel.department_id == department_id)
    if source is not None:
        query = query.filter(DailyReportModel.source == source)
    if status_filter is not None:
        query = query.filter(DailyReportModel.status == status_filter)
    if date_from is not None:
        query = query.filter(DailyReportModel.report_date >= date_from)
    if date_to is not None:
        query = query.filter(DailyReportModel.report_date <= date_to)
    if needs_help is not None:
        query = query.filter(DailyReportModel.needs_help == needs_help)
    return query.all()


@router.get("/{report_id}", response_model=DailyReport)
def get_admin_report(
    report_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> DailyReport:
    report = db.get(DailyReportModel, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily report not found")
    return report
