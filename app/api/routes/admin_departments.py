from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.daily_entry import DepartmentDailies, DepartmentDailyEmployee
from app.api.schemas.department import Department, DepartmentCreate, DepartmentUpdate
from app.db.session import get_db
from app.models import DailyEntry as DailyEntryModel
from app.models import Department as DepartmentModel
from app.models import Job as JobModel
from app.models import User as UserModel
from app.models.enums import UserRole
from app.services.dailies_grid import build_daily_days
from app.services.worker_statistics import days_in_range


router = APIRouter()


def _to_department_response(department: DepartmentModel, employees_count: int, jobs_count: int) -> Department:
    return Department(
        id=department.id,
        name=department.name,
        employees_count=employees_count,
        jobs_count=jobs_count,
    )


def _employees_count() -> object:
    return (
        select(func.count(UserModel.id))
        .where(UserModel.department_id == DepartmentModel.id)
        .correlate(DepartmentModel)
        .scalar_subquery()
    )


def _jobs_count() -> object:
    return (
        select(func.count(JobModel.id))
        .where(JobModel.department_id == DepartmentModel.id)
        .correlate(DepartmentModel)
        .scalar_subquery()
    )


def _get_department_or_404(db: Session, department_id: int) -> DepartmentModel:
    department = db.get(DepartmentModel, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@router.get("", response_model=List[Department])
def list_admin_departments(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[Department]:
    rows = (
        db.query(
            DepartmentModel,
            _employees_count().label("employees_count"),
            _jobs_count().label("jobs_count"),
        )
        .order_by(DepartmentModel.name.asc())
        .all()
    )
    return [
        _to_department_response(department, employees_count, jobs_count)
        for department, employees_count, jobs_count in rows
    ]


@router.get("/{department_id}", response_model=Department)
def get_admin_department(
    department_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> Department:
    row = (
        db.query(
            DepartmentModel,
            _employees_count().label("employees_count"),
            _jobs_count().label("jobs_count"),
        )
        .filter(DepartmentModel.id == department_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    department, employees_count, jobs_count = row
    return _to_department_response(department, employees_count, jobs_count)


@router.post("", response_model=Department, status_code=status.HTTP_201_CREATED)
def create_admin_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> Department:
    existing = db.query(DepartmentModel).filter(DepartmentModel.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department already exists")

    department = DepartmentModel(name=payload.name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return _to_department_response(department, 0, 0)


@router.put("/{department_id}", response_model=Department)
def update_admin_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> Department:
    department = _get_department_or_404(db, department_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(department, field, value)
    db.commit()
    db.refresh(department)
    employees_count = db.query(UserModel).filter(UserModel.department_id == department.id).count()
    jobs_count = db.query(JobModel).filter(JobModel.department_id == department.id).count()
    return _to_department_response(department, employees_count, jobs_count)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_department(
    department_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> None:
    department = _get_department_or_404(db, department_id)

    has_users = db.query(UserModel).filter(UserModel.department_id == department.id).first() is not None
    has_entries = db.query(DailyEntryModel).filter(DailyEntryModel.department_id == department.id).first() is not None
    if has_users or has_entries or department.jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete department with related users, jobs, or entries",
        )

    db.delete(department)
    db.commit()


@router.get("/{department_id}/dailies", response_model=DepartmentDailies)
def get_department_dailies(
    department_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> DepartmentDailies:
    department = _get_department_or_404(db, department_id)

    period_end = date_to or date.today()
    period_start = date_from or period_end - timedelta(days=6)
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from не может быть позже date_to",
        )

    employees = (
        db.query(UserModel)
        .filter(UserModel.department_id == department_id, UserModel.role == UserRole.EMPLOYEE.value)
        .order_by(UserModel.name.asc())
        .all()
    )
    entries = (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(
            DailyEntryModel.user_id.in_([employee.id for employee in employees] or [0]),
            DailyEntryModel.date >= period_start,
            DailyEntryModel.date <= period_end,
        )
        .all()
    )
    by_user: dict[int, dict[date, DailyEntryModel]] = {}
    for entry in entries:
        by_user.setdefault(entry.user_id, {})[entry.date] = entry

    period = days_in_range(period_start, period_end)

    return DepartmentDailies(
        department_id=department.id,
        department_name=department.name,
        date_from=period_start,
        date_to=period_end,
        employees=[
            DepartmentDailyEmployee(
                user_id=employee.id,
                user_name=employee.name,
                schedule_type=employee.schedule_type,
                work_days=employee.work_days,
                days=build_daily_days(employee, period, by_user.get(employee.id, {})),
            )
            for employee in employees
        ],
    )
