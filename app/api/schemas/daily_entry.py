from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, ScheduleType


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
    items: list[EntryItemInput] = []


class DailyEntry(BaseModel):
    id: int
    user_id: int
    department_id: int | None = None
    date: date
    day_type: DayType
    status: DailyEntryStatus
    submitted_at: datetime | None = None
    items: list[EntryItem] = []

    model_config = ConfigDict(from_attributes=True)


class OpenChain(BaseModel):
    chain_id: str
    title: str | None = None
    last_status: EntryItemStatus
    last_text: str | None = None
    last_date: date
    days_open: int
    link: str | None = None


class DayView(BaseModel):
    entry: DailyEntry | None = None
    open_chains: list[OpenChain] = []
    missing_days: list[date] = []


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
    entry: DailyEntry | None = None


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
