from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, OffReason, ScheduleType

OFF_REASON_NOTE_MAX_LENGTH = 200


class EntryItemInput(BaseModel):
    chain_id: UUID | None = None
    text: str | None = None
    status: EntryItemStatus
    link: str | None = None
    position: int | None = None


class EntryItem(BaseModel):
    id: int
    chain_id: str
    text: str | None = None
    status: EntryItemStatus
    link: str | None = None
    position: int

    model_config = ConfigDict(from_attributes=True)


class DailyEntryWrite(BaseModel):
    day_type: DayType = DayType.WORK
    off_reason: OffReason | None = None
    off_reason_note: str | None = Field(default=None, max_length=OFF_REASON_NOTE_MAX_LENGTH)
    items: list[EntryItemInput] = []


class BulkDayTypeWrite(BaseModel):
    dates: list[date]
    day_type: DayType = DayType.OFF
    off_reason: OffReason | None = None
    off_reason_note: str | None = Field(default=None, max_length=OFF_REASON_NOTE_MAX_LENGTH)


class DailyEntry(BaseModel):
    id: int
    user_id: int
    department_id: int | None = None
    date: date
    day_type: DayType
    off_reason: OffReason | None = None
    off_reason_note: str | None = None
    status: DailyEntryStatus
    submitted_at: datetime | None = None
    items: list[EntryItem] = []

    model_config = ConfigDict(from_attributes=True)


class AdminDailyEntry(DailyEntry):
    edited_at: datetime | None = None


class ChainPoint(BaseModel):
    date: date
    status: EntryItemStatus


class OpenChain(BaseModel):
    chain_id: str
    title: str | None = None
    last_status: EntryItemStatus
    last_text: str | None = None
    last_date: date
    days_open: int
    link: str | None = None
    history: list[ChainPoint] = []


class DayView(BaseModel):
    entry: DailyEntry | None = None
    open_chains: list[OpenChain] = []
    missing_days: list[date] = []
    editable_from: date
    editable: bool
    editable_until: date


class ChainItem(BaseModel):
    id: int
    entry_id: int
    date: date
    text: str | None = None
    status: EntryItemStatus
    link: str | None = None
    position: int


class ChainHistory(BaseModel):
    chain_id: str
    title: str | None = None
    last_status: EntryItemStatus
    first_date: date
    last_date: date
    items: list[ChainItem] = []


class DepartmentDailyDay(BaseModel):
    date: date
    is_working_day: bool
    entry: AdminDailyEntry | None = None


class DepartmentDailyEmployee(BaseModel):
    user_id: int
    user_name: str
    schedule_type: ScheduleType
    work_days: list[int] | None = None
    days: list[DepartmentDailyDay] = []


class DepartmentDailies(BaseModel):
    department_id: int
    department_name: str
    date_from: date
    date_to: date
    employees: list[DepartmentDailyEmployee] = []
