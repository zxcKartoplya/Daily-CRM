from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from app.api.schemas.daily_entry import DepartmentDailyDay
from app.models import DailyEntry, User
from app.services.schedule import is_working_day


def build_daily_days(
    employee: User,
    days: Sequence[date],
    entries_by_date: Mapping[date, DailyEntry],
) -> list[DepartmentDailyDay]:
    return [
        DepartmentDailyDay(
            date=day,
            is_working_day=is_working_day(employee, day),
            entry=entries_by_date.get(day),
        )
        for day in days
    ]
