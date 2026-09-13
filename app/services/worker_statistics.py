from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from fastapi import HTTPException, status

from app.api.schemas.analytics import WorkerStatistics
from app.models.enums import CLOSED_ITEM_STATUSES, DayState, EntryItemStatus
from app.services.daily_entries import group_by_chain
from app.services.day_state import completion_rate as day_completion_rate
from app.services.day_state import resolve_day_state
from app.services.schedule import is_working_day

STATISTICS_DEFAULT_DAYS = 30
STATISTICS_MAX_DAYS = 366
AVG_ITEMS_PRECISION = 2

NEUTRAL_STREAK_STATES = frozenset({DayState.REST, DayState.OFF})


def resolve_statistics_period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    period_end = date_to or date.today()
    period_start = date_from or period_end - timedelta(days=STATISTICS_DEFAULT_DAYS - 1)
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from не может быть позже date_to",
        )
    if (period_end - period_start).days + 1 > STATISTICS_MAX_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"период не может быть длиннее {STATISTICS_MAX_DAYS} дней",
        )
    return period_start, period_end


def days_in_range(start: date, end: date) -> list[date]:
    if start > end:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def calculate_worker_statistics(
    user,
    *,
    period_from: date,
    period_to: date,
    entries: Sequence,
    chain_rows: Sequence[tuple],
    today: date | None = None,
) -> WorkerStatistics:
    today = today or date.today()
    entries_by_date = {entry.date: entry for entry in entries}

    counts = {state: 0 for state in DayState}
    longest_streak = 0
    running = 0
    for day in days_in_range(period_from, period_to):
        state = resolve_day_state(user, day, entries_by_date.get(day))
        if is_working_day(user, day):
            counts[state] += 1
        if state is DayState.SUBMITTED:
            running += 1
            longest_streak = max(longest_streak, running)
        elif state not in NEUTRAL_STREAK_STATES:
            running = 0

    working_days = counts[DayState.SUBMITTED] + counts[DayState.DRAFT] + counts[DayState.MISSING] + counts[DayState.OFF]
    filled_days = counts[DayState.SUBMITTED] + counts[DayState.DRAFT]

    period_items = [
        item
        for day, entry in entries_by_date.items()
        if period_from <= day <= period_to
        for item in entry.items
    ]
    done_items_count = sum(1 for item in period_items if item.status == EntryItemStatus.DONE.value)
    blockers_count = sum(1 for item in period_items if item.status == EntryItemStatus.BLOCKED.value)

    chains = group_by_chain(list(chain_rows))
    open_chains_count = sum(1 for rows in chains.values() if rows[-1][0].status not in CLOSED_ITEM_STATUSES)
    dropped_chains_count = sum(
        1 for rows in chains.values() if rows[-1][0].status == EntryItemStatus.DROPPED.value
    )

    submitted_at = [entry.submitted_at for entry in entries if entry.submitted_at is not None]

    return WorkerStatistics(
        user_id=user.id,
        period_from=period_from,
        period_to=period_to,
        working_days=working_days,
        submitted_count=counts[DayState.SUBMITTED],
        draft_count=counts[DayState.DRAFT],
        missing_count=counts[DayState.MISSING],
        off_count=counts[DayState.OFF],
        completion_rate=day_completion_rate(counts[DayState.SUBMITTED], working_days),
        streak=current_streak(user, entries_by_date, today),
        longest_streak=longest_streak,
        open_chains_count=open_chains_count,
        blockers_count=blockers_count,
        dropped_chains_count=dropped_chains_count,
        done_items_count=done_items_count,
        avg_items_per_day=(
            round(len(period_items) / filled_days, AVG_ITEMS_PRECISION) if filled_days else 0.0
        ),
        last_entry_at=max(submitted_at) if submitted_at else None,
    )


def current_streak(user, entries_by_date: dict[date, object], today: date) -> int:
    if not entries_by_date:
        return 0

    earliest = min(entries_by_date)
    streak = 0
    current = today
    while current >= earliest:
        state = resolve_day_state(user, current, entries_by_date.get(current))
        if state is DayState.SUBMITTED:
            streak += 1
        elif state not in NEUTRAL_STREAK_STATES and current != today:
            break
        current -= timedelta(days=1)
    return streak
