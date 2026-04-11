from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.daily_report import DailyReportCreate, DailyReportUpdate
from app.models import DailyReport as DailyReportModel
from app.models import User as UserModel
from app.models.enums import DailyReportSource, DailyReportStatus


def create_daily_report(
    db: Session,
    *,
    user: UserModel,
    payload: DailyReportCreate,
) -> DailyReportModel:
    existing = (
        db.query(DailyReportModel)
        .filter(
            DailyReportModel.user_id == user.id,
            DailyReportModel.report_date == payload.report_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily report for this date already exists",
        )

    report = DailyReportModel(
        user_id=user.id,
        department_id=user.department_id,
        source=payload.source.value,
        status=payload.status.value,
        report_date=payload.report_date,
        submitted_at=datetime.utcnow(),
        yesterday_text=payload.yesterday_text,
        today_text=payload.today_text,
        blockers_text=payload.blockers_text,
        mood=payload.mood,
        self_rating=payload.self_rating,
        needs_help=payload.needs_help,
    )
    db.add(report)
    db.flush()
    return report


def update_daily_report(report: DailyReportModel, payload: DailyReportUpdate, *, user: UserModel) -> DailyReportModel:
    update_data = payload.dict(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    if "report_date" in update_data and update_data["report_date"] is not None:
        report.department_id = user.department_id

    for field, value in update_data.items():
        setattr(report, field, value)

    if payload.status is None and report.status == DailyReportStatus.DRAFT.value:
        report.status = DailyReportStatus.SUBMITTED.value
    report.source = report.source or DailyReportSource.INTERNAL_WEB.value
    return report


def build_internal_chat_report_payload(message_text: str, report_date: date | None = None) -> DailyReportCreate:
    return DailyReportCreate(
        report_date=report_date or date.today(),
        today_text=message_text,
        source=DailyReportSource.INTERNAL_WEB,
        status=DailyReportStatus.SUBMITTED,
    )
