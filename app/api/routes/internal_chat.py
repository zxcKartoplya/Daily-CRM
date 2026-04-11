from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.daily_report import DailyReportUpdate
from app.api.schemas.internal_chat import InternalChatMessage, InternalChatMessageCreate
from app.db.session import get_db
from app.models import DailyReport as DailyReportModel
from app.models import InternalChatMessage as InternalChatMessageModel
from app.models import User as UserModel
from app.services.daily_reports import build_internal_chat_report_payload, create_daily_report, update_daily_report


router = APIRouter()


@router.get("/messages", response_model=List[InternalChatMessage])
def list_internal_chat_messages(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> List[InternalChatMessage]:
    return (
        db.query(InternalChatMessageModel)
        .filter(InternalChatMessageModel.user_id == current_user.id)
        .order_by(InternalChatMessageModel.created_at.desc())
        .all()
    )


@router.post("/messages", response_model=InternalChatMessage, status_code=status.HTTP_201_CREATED)
def create_internal_chat_message(
    payload: InternalChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> InternalChatMessage:
    message = InternalChatMessageModel(
        user_id=current_user.id,
        message_text=payload.message_text,
    )
    db.add(message)
    db.flush()

    if payload.daily_report is not None:
        report_date = payload.daily_report.report_date or date.today()
        existing_report = (
            db.query(DailyReportModel)
            .filter(
                DailyReportModel.user_id == current_user.id,
                DailyReportModel.report_date == report_date,
            )
            .first()
        )
        if existing_report:
            report_update = DailyReportUpdate(
                yesterday_text=payload.daily_report.yesterday_text,
                today_text=payload.daily_report.today_text,
                blockers_text=payload.daily_report.blockers_text,
                mood=payload.daily_report.mood,
                self_rating=payload.daily_report.self_rating,
                needs_help=payload.daily_report.needs_help,
                status=payload.daily_report.status,
            )
            update_daily_report(existing_report, report_update, user=current_user)
            report = existing_report
        else:
            report_payload = build_internal_chat_report_payload(
                payload.message_text,
                report_date=report_date,
            )
            if payload.daily_report.yesterday_text is not None:
                report_payload.yesterday_text = payload.daily_report.yesterday_text
            if payload.daily_report.today_text is not None:
                report_payload.today_text = payload.daily_report.today_text
            if payload.daily_report.blockers_text is not None:
                report_payload.blockers_text = payload.daily_report.blockers_text
            if payload.daily_report.mood is not None:
                report_payload.mood = payload.daily_report.mood
            if payload.daily_report.self_rating is not None:
                report_payload.self_rating = payload.daily_report.self_rating
            report_payload.needs_help = payload.daily_report.needs_help
            report_payload.source = payload.daily_report.source
            report_payload.status = payload.daily_report.status
            report = create_daily_report(db, user=current_user, payload=report_payload)

        message.parsed_to_daily_report = True
        message.daily_report_id = report.id

    db.commit()
    db.refresh(message)
    return message
