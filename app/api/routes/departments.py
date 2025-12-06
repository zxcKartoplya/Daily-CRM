from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.department import Department, DepartmentCreate, DepartmentUpdate
from app.db.session import get_db
from app.models import (
    Department as DepartmentModel,
    Admin as AdminModel,
    Job as JobModel,
    User as UserModel,
)


router = APIRouter()


def _to_department_response(
    department: DepartmentModel, employees_count: int, admin: AdminModel
) -> Department:
    return Department(
        id=department.id,
        name=department.name,
        admin_id=department.admin_id,
        admin_name=admin.full_name,
        employees_count=employees_count,
    )


def _get_department_with_counts(
    db: Session, department_id: int, current_admin: AdminModel
) -> tuple[DepartmentModel, int] | None:
    return (
        db.query(DepartmentModel, func.count(UserModel.id).label("employees_count"))
        .outerjoin(JobModel, JobModel.department_id == DepartmentModel.id)
        .outerjoin(UserModel, UserModel.job_id == JobModel.id)
        .filter(DepartmentModel.id == department_id, DepartmentModel.admin_id == current_admin.id)
        .group_by(DepartmentModel.id)
        .first()
    )


def _get_department_response(
    db: Session, department_id: int, current_admin: AdminModel
) -> Department:
    result = _get_department_with_counts(db, department_id, current_admin)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    department, employees_count = result
    return _to_department_response(department, employees_count, current_admin)


@router.get("", response_model=List[Department])
def list_departments(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Department]:
    departments = (
        db.query(DepartmentModel, func.count(UserModel.id).label("employees_count"))
        .outerjoin(JobModel, JobModel.department_id == DepartmentModel.id)
        .outerjoin(UserModel, UserModel.job_id == JobModel.id)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .group_by(DepartmentModel.id)
        .all()
    )
    return [
        _to_department_response(department, employees_count, current_admin)
        for department, employees_count in departments
    ]


@router.get("/{department_id}", response_model=Department)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    return _get_department_response(db, department_id, current_admin)


@router.post("", response_model=Department, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    department = DepartmentModel(**payload.dict(), admin_id=current_admin.id)
    db.add(department)
    db.commit()
    db.refresh(department)
    # Reuse the same response shape with aggregated employees count
    return _get_department_response(db, department.id, current_admin)


@router.put("/{department_id}", response_model=Department)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    department_with_count = _get_department_with_counts(db, department_id, current_admin)
    if not department_with_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    department, _ = department_with_count

    for field, value in payload.dict().items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)
    return _get_department_response(db, department.id, current_admin)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> None:
    department = db.query(DepartmentModel).get(department_id)
    if not department or department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    db.delete(department)
    db.commit()
