from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.daily_report import DailyReportCreate, DailyReportUpdate
from app.models import DailyReport as DailyReportModel
from app.models import DailyReportTask as DailyReportTaskModel
from app.models import User as UserModel
from app.models.enums import DailyReportSource, DailyReportStatus, DailyReportTaskSlot


def _create_tasks(db: Session, report_id: int, tasks: list) -> None:
    for task_data in tasks:
        task = DailyReportTaskModel(
            report_id=report_id,
            task_id=task_data.task_id,
            task_text=task_data.task_text,
            slot=task_data.slot.value,
        )
        db.add(task)


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
        blockers_text=payload.blockers_text,
        blocker_type=payload.blocker_type.value if payload.blocker_type else None,
        self_rating=payload.self_rating,
        needs_help=payload.needs_help,
    )
    db.add(report)
    db.flush()

    _create_tasks(db, report.id, payload.tasks)
    return report


def update_daily_report(
    db: Session,
    report: DailyReportModel,
    payload: DailyReportUpdate,
    *,
    user: UserModel,
) -> DailyReportModel:
    tasks = payload.tasks  # Pydantic objects before dump
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("tasks", None)

    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    if "blocker_type" in update_data:
        bt = update_data["blocker_type"]
        update_data["blocker_type"] = bt.value if bt is not None else None

    if "report_date" in update_data and update_data["report_date"] is not None:
        report.department_id = user.department_id

    for field, value in update_data.items():
        setattr(report, field, value)

    if payload.status is None and report.status == DailyReportStatus.DRAFT.value:
        report.status = DailyReportStatus.SUBMITTED.value
    report.source = report.source or DailyReportSource.INTERNAL_WEB.value

    if tasks is not None:
        db.query(DailyReportTaskModel).filter(DailyReportTaskModel.report_id == report.id).delete()
        _create_tasks(db, report.id, tasks)

    return report


def build_internal_chat_report_payload(message_text: str, report_date: date | None = None) -> DailyReportCreate:
    from app.api.schemas.daily_report import DailyReportTaskCreate

    return DailyReportCreate(
        report_date=report_date or date.today(),
        source=DailyReportSource.INTERNAL_WEB,
        status=DailyReportStatus.SUBMITTED,
        tasks=[DailyReportTaskCreate(task_text=message_text, slot=DailyReportTaskSlot.DONE)],
    )
