from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from app.api.schemas.analytics import WorkerStatistics
from app.api.schemas.daily_entry import DepartmentDailyDay, DepartmentDailyStats
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


def project_daily_stats(statistics: WorkerStatistics) -> DepartmentDailyStats:
    return DepartmentDailyStats(
        working_days=statistics.working_days,
        submitted=statistics.submitted_count,
        draft=statistics.draft_count,
        missing=statistics.missing_count,
        off=statistics.off_count,
        completion_rate=statistics.completion_rate,
        streak=statistics.streak,
        blockers=statistics.blockers_count,
        done_items=statistics.done_items_count,
    )
