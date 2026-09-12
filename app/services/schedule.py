from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Job as JobModel
from app.models.enums import DEFAULT_WORK_DAYS, ScheduleType


def _resolve_type(value: ScheduleType | str | None) -> ScheduleType:
    if value is None:
        return ScheduleType.WEEKLY
    if isinstance(value, ScheduleType):
        return value
    try:
        return ScheduleType(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown schedule_type: {value}",
        )


def _resolve_work_days(work_days: list[int] | None) -> list[int]:
    if not work_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="work_days must contain at least one weekday for a weekly schedule",
        )
    days = sorted({int(day) for day in work_days})
    if days[0] < 1 or days[-1] > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="work_days must contain weekday numbers from 1 (Monday) to 7 (Sunday)",
        )
    return days


def normalize_schedule(
    schedule_type: ScheduleType | str | None,
    work_days: list[int] | None,
) -> tuple[str, list[int] | None]:
    resolved = _resolve_type(schedule_type)
    if resolved is ScheduleType.NONE:
        return resolved.value, None
    return resolved.value, _resolve_work_days(DEFAULT_WORK_DAYS if work_days is None else work_days)


def schedule_for_new_user(
    db: Session,
    *,
    job_id: int | None,
    schedule_type: ScheduleType | str | None = None,
    work_days: list[int] | None = None,
) -> tuple[str, list[int] | None]:
    job = db.get(JobModel, job_id) if job_id is not None else None

    inherited_type = schedule_type if schedule_type is not None else (job.schedule_type if job else None)
    if work_days is not None:
        inherited_days = work_days
    elif job is not None and _resolve_type(job.schedule_type) is ScheduleType.WEEKLY:
        inherited_days = list(job.work_days) if job.work_days else DEFAULT_WORK_DAYS
    else:
        inherited_days = None

    return normalize_schedule(inherited_type, inherited_days)


def apply_schedule_update(model, update_data: dict) -> None:
    if "schedule_type" not in update_data and "work_days" not in update_data:
        return

    schedule_type = update_data.pop("schedule_type", None) or model.schedule_type
    work_days = update_data.pop("work_days", model.work_days)
    if work_days is None and _resolve_type(schedule_type) is ScheduleType.WEEKLY:
        work_days = list(model.work_days) if model.work_days else DEFAULT_WORK_DAYS

    model.schedule_type, model.work_days = normalize_schedule(schedule_type, work_days)


def has_schedule(user) -> bool:
    return _resolve_type(user.schedule_type) is ScheduleType.WEEKLY


def is_working_day(user, day: date) -> bool:
    if not has_schedule(user):
        return False
    return day.isoweekday() in (user.work_days or [])


def working_days_in_range(user, start: date, end: date) -> list[date]:
    if not has_schedule(user) or start > end:
        return []

    days: list[date] = []
    current = start
    while current <= end:
        if is_working_day(user, current):
            days.append(current)
        current += timedelta(days=1)
    return days
