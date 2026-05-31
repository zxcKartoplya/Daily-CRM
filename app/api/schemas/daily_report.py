from datetime import date, datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import BlockerType, DailyReportSource, DailyReportStatus, DailyReportTaskSlot


class DailyReportTaskCreate(BaseModel):
    task_id: int | None = None
    task_text: str | None = None
    slot: DailyReportTaskSlot

    @model_validator(mode="after")
    def check_task_ref(self) -> "DailyReportTaskCreate":
        if self.task_id is None and not self.task_text:
            raise ValueError("Either task_id or task_text must be provided")
        return self


class DailyReportTask(DailyReportTaskCreate):
    id: int
    report_id: int

    model_config = ConfigDict(from_attributes=True)


class DailyReportBase(BaseModel):
    report_date: date
    blockers_text: str | None = None
    blocker_type: BlockerType | None = None
    self_rating: int | None = Field(default=None, ge=1, le=10)
    needs_help: bool = False


class DailyReportCreate(DailyReportBase):
    source: DailyReportSource = DailyReportSource.INTERNAL_WEB
    status: DailyReportStatus = DailyReportStatus.SUBMITTED
    tasks: List[DailyReportTaskCreate] = []


class DailyReportUpdate(BaseModel):
    report_date: date | None = None
    blockers_text: str | None = None
    blocker_type: BlockerType | None = None
    self_rating: int | None = Field(default=None, ge=1, le=10)
    needs_help: bool | None = None
    status: DailyReportStatus | None = None
    tasks: List[DailyReportTaskCreate] | None = None


class DailyReport(DailyReportBase):
    id: int
    user_id: int
    department_id: int | None = None
    source: DailyReportSource
    status: DailyReportStatus
    submitted_at: datetime
    tasks: List[DailyReportTask] = []

    model_config = ConfigDict(from_attributes=True)
