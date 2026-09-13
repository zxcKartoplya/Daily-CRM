from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Mapping, Sequence

from app.models.enums import DailyEntryStatus, DayState, DayType, UserRole, UserStatus
from app.services.schedule import is_working_day

COMPLETION_RATE_PRECISION = 4


def resolve_day_state(user, day: date, entry=None) -> DayState:
    if entry is not None:
        if entry.day_type == DayType.OFF.value:
            return DayState.OFF
        if entry.status == DailyEntryStatus.SUBMITTED.value:
            return DayState.SUBMITTED
        return DayState.DRAFT
    if not is_working_day(user, day):
        return DayState.REST
    return DayState.MISSING


def is_employed_on(user, day: date) -> bool:
    created_at = getattr(user, "created_at", None)
    if created_at is None:
        return True
    return created_at.date() <= day


def is_tracked_employee(user) -> bool:
    return user.role == UserRole.EMPLOYEE.value and user.status != UserStatus.INACTIVE.value


def scheduled_employees(users: Iterable, day: date) -> list:
    return [
        user
        for user in users
        if is_tracked_employee(user)
        and is_employed_on(user, day)
        and is_working_day(user, day)
    ]


def count_day_states(users: Sequence, day: date, entries_by_user: Mapping[int, object]) -> dict[DayState, int]:
    counts = {state: 0 for state in DayState}
    for user in users:
        counts[resolve_day_state(user, day, entries_by_user.get(user.id))] += 1
    return counts


def completion_rate(submitted: int, working_employees: int) -> float | None:
    if working_employees <= 0:
        return None
    return round(submitted / working_employees, COMPLETION_RATE_PRECISION)


@dataclass(frozen=True)
class DayTotals:
    day: date
    working_employees: int
    counts: dict[DayState, int]


def day_totals(
    users: Sequence,
    period_start: date,
    period_end: date,
    entries_by_day: Mapping[date, Mapping[int, object]],
) -> list[DayTotals]:
    totals: list[DayTotals] = []
    for offset in range((period_end - period_start).days + 1):
        day = period_start + timedelta(days=offset)
        working = scheduled_employees(users, day)
        totals.append(
            DayTotals(
                day=day,
                working_employees=len(working),
                counts=count_day_states(working, day, entries_by_day.get(day, {})),
            )
        )
    return totals
