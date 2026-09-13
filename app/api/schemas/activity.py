from datetime import date

from pydantic import BaseModel

from app.api.schemas.daily_entry import ChainPoint
from app.models.enums import ActivityPeriod, ChainOutcome, EntryItemStatus


class ActivityChain(BaseModel):
    chain_id: str
    title: str | None = None
    link: str | None = None
    first_date: date
    last_date: date
    last_status: EntryItemStatus
    outcome: ChainOutcome
    closed_date: date | None = None
    days_total: int
    blocked_days: int
    started_in_period: bool
    closed_in_period: bool
    history: list[ChainPoint] = []


class ActivitySummary(BaseModel):
    chains_count: int
    started_count: int
    done_count: int
    dropped_count: int
    open_count: int
    blocked_chains_count: int
    blocked_days: int
    avg_days_to_done: float | None = None


class EmployeeActivity(BaseModel):
    period: ActivityPeriod
    date_from: date
    date_to: date
    summary: ActivitySummary
    chains: list[ActivityChain] = []
