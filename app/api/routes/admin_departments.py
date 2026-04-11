from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.department import Department, DepartmentCreate, DepartmentUpdate
from app.db.session import get_db
from app.models import DailyReport as DailyReportModel
from app.models import Department as DepartmentModel
from app.models import User as UserModel


router = APIRouter()


def _to_department_response(department: DepartmentModel, employees_count: int) -> Department:
    return Department(
        id=department.id,
        name=department.name,
        employees_count=employees_count,
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
            func.count(UserModel.id).label("employees_count"),
        )
        .outerjoin(UserModel, UserModel.department_id == DepartmentModel.id)
        .group_by(DepartmentModel.id)
        .order_by(DepartmentModel.name.asc())
        .all()
    )
    return [_to_department_response(department, employees_count) for department, employees_count in rows]


@router.get("/{department_id}", response_model=Department)
def get_admin_department(
    department_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> Department:
    row = (
        db.query(
            DepartmentModel,
            func.count(UserModel.id).label("employees_count"),
        )
        .outerjoin(UserModel, UserModel.department_id == DepartmentModel.id)
        .filter(DepartmentModel.id == department_id)
        .group_by(DepartmentModel.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    department, employees_count = row
    return _to_department_response(department, employees_count)


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
    return _to_department_response(department, 0)


@router.put("/{department_id}", response_model=Department)
def update_admin_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> Department:
    department = _get_department_or_404(db, department_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(department, field, value)
    db.commit()
    db.refresh(department)
    employees_count = db.query(UserModel).filter(UserModel.department_id == department.id).count()
    return _to_department_response(department, employees_count)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_department(
    department_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> None:
    department = _get_department_or_404(db, department_id)

    has_users = db.query(UserModel).filter(UserModel.department_id == department.id).first() is not None
    has_reports = db.query(DailyReportModel).filter(DailyReportModel.department_id == department.id).first() is not None
    if has_users or has_reports or department.jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete department with related users, jobs, or reports",
        )

    db.delete(department)
    db.commit()
