from collections import defaultdict
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.analytics import (
    AnalyticsOverview,
    AnalyticsTimeseriesPoint,
    DepartmentAnalytics,
    TodayState,
)
from app.db.session import get_db
from app.models import DailyEntry as DailyEntryModel
from app.models import Department as DepartmentModel
from app.models import EntryItem as EntryItemModel
from app.models import User as UserModel
from app.models.enums import CLOSED_ITEM_STATUSES, DayState, EntryItemStatus, UserRole
from app.services.daily_entries import chain_summaries
from app.services.day_state import (
    completion_rate,
    day_totals,
    is_employed_on,
    is_tracked_employee,
    resolve_day_state,
)

router = APIRouter()

OVERVIEW_WINDOW_DAYS = 30
TIMESERIES_DEFAULT_DAYS = 30
TIMESERIES_MAX_DAYS = 366


def _entries_by_day(
    db: Session,
    employees: List[UserModel],
    period_start: date,
    period_end: date,
) -> dict[date, dict[int, DailyEntryModel]]:
    by_day: dict[date, dict[int, DailyEntryModel]] = defaultdict(dict)
    if not employees:
        return by_day
    entries = (
        db.query(DailyEntryModel)
        .filter(
            DailyEntryModel.user_id.in_([employee.id for employee in employees]),
            DailyEntryModel.date >= period_start,
            DailyEntryModel.date <= period_end,
        )
        .all()
    )
    for entry in entries:
        by_day[entry.date][entry.user_id] = entry
    return by_day


def _blocked_items_query(db: Session, since: date | None = None):
    query = (
        db.query(func.count(EntryItemModel.id))
        .join(DailyEntryModel, EntryItemModel.entry_id == DailyEntryModel.id)
        .filter(EntryItemModel.status == EntryItemStatus.BLOCKED.value)
    )
    if since is not None:
        query = query.filter(DailyEntryModel.date >= since)
    return query


@router.get("/overview", response_model=AnalyticsOverview)
def get_admin_analytics_overview(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> AnalyticsOverview:
    today = date.today()
    window_start = today - timedelta(days=OVERVIEW_WINDOW_DAYS - 1)

    employees = [
        user
        for user in db.query(UserModel).filter(UserModel.role == UserRole.EMPLOYEE.value).all()
        if is_tracked_employee(user)
    ]
    departments_count = db.query(DepartmentModel).count()
    entries_count = db.query(DailyEntryModel).count()
    entries_today = db.query(DailyEntryModel).filter(DailyEntryModel.date == today).count()
    last_entry_at = db.query(func.max(DailyEntryModel.submitted_at)).scalar()

    open_chains_count = sum(
        1 for _, _, _, last_status in chain_summaries(db) if last_status not in CLOSED_ITEM_STATUSES
    )
    blocked_items = _blocked_items_query(db, since=window_start).scalar() or 0

    totals = day_totals(employees, window_start, today, _entries_by_day(db, employees, window_start, today))
    submitted = sum(total.counts[DayState.SUBMITTED] for total in totals)
    working_employees = sum(total.working_employees for total in totals)

    return AnalyticsOverview(
        employees_count=len(employees),
        departments_count=departments_count,
        entries_count=entries_count,
        entries_today=entries_today,
        open_chains_count=open_chains_count,
        blocked_items_last_30_days=int(blocked_items),
        last_entry_at=last_entry_at,
        completion_rate_last_30_days=completion_rate(submitted, working_employees),
    )


@router.get("/departments", response_model=List[DepartmentAnalytics])
def get_department_analytics(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[DepartmentAnalytics]:
    employee_counts = dict(
        db.query(UserModel.department_id, func.count(UserModel.id))
        .filter(UserModel.role == UserRole.EMPLOYEE.value)
        .group_by(UserModel.department_id)
        .all()
    )
    entry_counts = dict(
        db.query(DailyEntryModel.department_id, func.count(DailyEntryModel.id))
        .group_by(DailyEntryModel.department_id)
        .all()
    )
    blocked_counts = dict(
        db.query(DailyEntryModel.department_id, func.count(EntryItemModel.id))
        .join(EntryItemModel, EntryItemModel.entry_id == DailyEntryModel.id)
        .filter(EntryItemModel.status == EntryItemStatus.BLOCKED.value)
        .group_by(DailyEntryModel.department_id)
        .all()
    )

    open_counts: dict[int | None, int] = defaultdict(int)
    for _, department_id, _, last_status in chain_summaries(db):
        if last_status not in CLOSED_ITEM_STATUSES:
            open_counts[department_id] += 1

    departments = db.query(DepartmentModel).order_by(DepartmentModel.name.asc()).all()
    return [
        DepartmentAnalytics(
            department_id=department.id,
            department_name=department.name,
            employees_count=int(employee_counts.get(department.id, 0)),
            entries_count=int(entry_counts.get(department.id, 0)),
            open_chains_count=int(open_counts.get(department.id, 0)),
            blocked_items_count=int(blocked_counts.get(department.id, 0)),
        )
        for department in departments
    ]


def _resolve_period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    period_end = date_to or date.today()
    period_start = date_from or period_end - timedelta(days=TIMESERIES_DEFAULT_DAYS - 1)
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from не может быть позже date_to",
        )
    if (period_end - period_start).days + 1 > TIMESERIES_MAX_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"период не может быть длиннее {TIMESERIES_MAX_DAYS} дней",
        )
    return period_start, period_end


@router.get("/timeseries", response_model=List[AnalyticsTimeseriesPoint])
def get_analytics_timeseries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[AnalyticsTimeseriesPoint]:
    period_start, period_end = _resolve_period(date_from, date_to)

    if department_id is not None and db.get(DepartmentModel, department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    employees_query = db.query(UserModel).filter(UserModel.role == UserRole.EMPLOYEE.value)
    if department_id is not None:
        employees_query = employees_query.filter(UserModel.department_id == department_id)
    employees = employees_query.all()

    entries_by_day = _entries_by_day(db, employees, period_start, period_end)
    return [
        AnalyticsTimeseriesPoint(
            date=total.day,
            working_employees=total.working_employees,
            submitted=total.counts[DayState.SUBMITTED],
            draft=total.counts[DayState.DRAFT],
            missing=total.counts[DayState.MISSING],
            off=total.counts[DayState.OFF],
            completion_rate=completion_rate(total.counts[DayState.SUBMITTED], total.working_employees),
        )
        for total in day_totals(employees, period_start, period_end, entries_by_day)
    ]


@router.get("/today", response_model=List[TodayState])
def get_analytics_today(
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[TodayState]:
    today = date.today()

    if department_id is not None and db.get(DepartmentModel, department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    users_query = (
        db.query(UserModel)
        .options(joinedload(UserModel.department), joinedload(UserModel.job))
        .filter(UserModel.role == UserRole.EMPLOYEE.value)
    )
    if department_id is not None:
        users_query = users_query.filter(UserModel.department_id == department_id)
    employees = [
        user for user in users_query.all() if is_tracked_employee(user) and is_employed_on(user, today)
    ]
    if not employees:
        return []

    entries_by_user = {
        entry.user_id: entry
        for entry in db.query(DailyEntryModel)
        .filter(
            DailyEntryModel.user_id.in_([employee.id for employee in employees]),
            DailyEntryModel.date == today,
        )
        .all()
    }

    states: List[TodayState] = []
    for employee in sorted(employees, key=lambda user: (user.name, user.id)):
        entry = entries_by_user.get(employee.id)
        states.append(
            TodayState(
                user_id=employee.id,
                user_name=employee.name,
                department_id=employee.department_id,
                department_name=employee.department.name if employee.department else None,
                job_name=employee.job.name if employee.job else None,
                state=resolve_day_state(employee, today, entry),
                entry_id=entry.id if entry else None,
                submitted_at=entry.submitted_at if entry else None,
            )
        )
    return states
