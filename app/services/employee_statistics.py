from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.api.schemas.analytics import EmployeeStatistics
from app.models import DailyEntry as DailyEntryModel
from app.models.enums import CLOSED_ITEM_STATUSES, DayType, EntryItemStatus
from app.services.daily_entries import chain_rows, group_by_chain
from app.services.schedule import has_schedule, is_working_day

STATISTICS_WINDOW_DAYS = 30


def calculate_employee_statistics(db: Session, user) -> EmployeeStatistics:
    entries = (
        db.query(DailyEntryModel)
        .filter(DailyEntryModel.user_id == user.id)
        .order_by(DailyEntryModel.date.desc())
        .all()
    )
    day_types = {entry.date: entry.day_type for entry in entries}

    rows = chain_rows(db, user.id)
    chains = group_by_chain(rows)
    open_chains_count = sum(
        1 for chain in chains.values() if chain[-1][0].status not in CLOSED_ITEM_STATUSES
    )
    dropped_chains_count = sum(
        1 for chain in chains.values() if chain[-1][0].status == EntryItemStatus.DROPPED.value
    )
    blockers_count = sum(
        1 for item, _ in rows if item.status == EntryItemStatus.BLOCKED.value
    )

    submitted = [entry.submitted_at for entry in entries if entry.submitted_at is not None]

    return EmployeeStatistics(
        user_id=user.id,
        streak=_calculate_streak(user, day_types),
        completion_rate=completion_rate(user, day_types),
        open_chains_count=open_chains_count,
        blockers_count=blockers_count,
        dropped_chains_count=dropped_chains_count,
        last_entry_at=max(submitted) if submitted else None,
    )


def _calculate_streak(user, day_types: dict[date, str]) -> int:
    if not day_types:
        return 0

    streak = 0
    current = date.today()
    if current not in day_types:
        current -= timedelta(days=1)

    scheduled = has_schedule(user)
    while current >= min(day_types):
        if scheduled and not is_working_day(user, current):
            current -= timedelta(days=1)
            continue

        day_type = day_types.get(current)
        if day_type == DayType.OFF.value:
            current -= timedelta(days=1)
            continue
        if day_type is None:
            break

        streak += 1
        current -= timedelta(days=1)
    return streak


def completion_rate(user, day_types: dict[date, str]) -> float | None:
    if not has_schedule(user):
        return None

    today = date.today()
    window_start = today - timedelta(days=STATISTICS_WINDOW_DAYS - 1)

    expected = 0
    written = 0
    current = window_start
    while current <= today:
        if is_working_day(user, current) and day_types.get(current) != DayType.OFF.value:
            expected += 1
            if day_types.get(current) == DayType.WORK.value:
                written += 1
        current += timedelta(days=1)

    if expected == 0:
        return None
    return round(written / expected, 4)
