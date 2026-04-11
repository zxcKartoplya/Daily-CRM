from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import DailyReportSource, DailyReportStatus


class DailyReportBase(BaseModel):
    report_date: date
    yesterday_text: str | None = None
    today_text: str | None = None
    blockers_text: str | None = None
    mood: str | None = None
    self_rating: int | None = Field(default=None, ge=1, le=10)
    needs_help: bool = False


class DailyReportCreate(DailyReportBase):
    source: DailyReportSource = DailyReportSource.INTERNAL_WEB
    status: DailyReportStatus = DailyReportStatus.SUBMITTED


class DailyReportUpdate(BaseModel):
    report_date: date | None = None
    yesterday_text: str | None = None
    today_text: str | None = None
    blockers_text: str | None = None
    mood: str | None = None
    self_rating: int | None = Field(default=None, ge=1, le=10)
    needs_help: bool | None = None
    status: DailyReportStatus | None = None


class DailyReport(DailyReportBase):
    id: int
    user_id: int
    department_id: int | None = None
    source: DailyReportSource
    status: DailyReportStatus
    submitted_at: datetime

    class Config:
        from_attributes = True
