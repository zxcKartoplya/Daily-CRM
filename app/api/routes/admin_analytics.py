from collections import defaultdict
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.analytics import AnalyticsOverview, DepartmentAnalytics
from app.db.session import get_db
from app.models import DailyEntry as DailyEntryModel
from app.models import Department as DepartmentModel
from app.models import EntryItem as EntryItemModel
from app.models import User as UserModel
from app.models.enums import CLOSED_ITEM_STATUSES, EntryItemStatus, UserRole
from app.services.daily_entries import chain_summaries
from app.services.employee_statistics import STATISTICS_WINDOW_DAYS, completion_rate

router = APIRouter()


def _day_types_by_user(db: Session, window_start: date) -> dict[int, dict[date, str]]:
    rows = (
        db.query(DailyEntryModel.user_id, DailyEntryModel.date, DailyEntryModel.day_type)
        .filter(DailyEntryModel.date >= window_start)
        .all()
    )
    by_user: dict[int, dict[date, str]] = defaultdict(dict)
    for user_id, day, day_type in rows:
        by_user[user_id][day] = day_type
    return by_user


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
    window_start = today - timedelta(days=STATISTICS_WINDOW_DAYS - 1)

    employees = db.query(UserModel).filter(UserModel.role == UserRole.EMPLOYEE.value).all()
    departments_count = db.query(DepartmentModel).count()
    entries_count = db.query(DailyEntryModel).count()
    entries_today = db.query(DailyEntryModel).filter(DailyEntryModel.date == today).count()
    last_entry_at = db.query(func.max(DailyEntryModel.submitted_at)).scalar()

    open_chains_count = sum(
        1 for _, _, _, last_status in chain_summaries(db) if last_status not in CLOSED_ITEM_STATUSES
    )
    blocked_items = _blocked_items_query(db, since=window_start).scalar() or 0

    day_types = _day_types_by_user(db, window_start)
    rates = [
        rate
        for employee in employees
        if (rate := completion_rate(employee, day_types.get(employee.id, {}))) is not None
    ]

    return AnalyticsOverview(
        employees_count=len(employees),
        departments_count=departments_count,
        entries_count=entries_count,
        entries_today=entries_today,
        open_chains_count=open_chains_count,
        blocked_items_last_30_days=int(blocked_items),
        last_entry_at=last_entry_at,
        completion_rate_last_30_days=round(sum(rates) / len(rates), 4) if rates else None,
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
