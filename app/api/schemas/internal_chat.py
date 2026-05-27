from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.api.schemas.daily_report import DailyReport, DailyReportCreate


class InternalChatDailyReportPayload(DailyReportCreate):
    report_date: date | None = None


class InternalChatMessageCreate(BaseModel):
    message_text: str
    daily_report: InternalChatDailyReportPayload | None = None


class InternalChatMessage(BaseModel):
    id: int
    user_id: int
    message_text: str
    created_at: datetime
    parsed_to_daily_report: bool
    daily_report_id: int | None = None
    daily_report: DailyReport | None = None   # ← ДОБАВЬ

    model_config = ConfigDict(from_attributes=True)
