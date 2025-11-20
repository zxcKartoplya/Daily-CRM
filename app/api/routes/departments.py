from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.department import Department, DepartmentCreate, DepartmentUpdate
from app.db.session import get_db
from app.models import Department as DepartmentModel, Admin as AdminModel


router = APIRouter()


@router.get("/", response_model=List[Department])
def list_departments(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Department]:
    return db.query(DepartmentModel).filter(DepartmentModel.admin_id == current_admin.id).all()


@router.get("/{department_id}", response_model=Department)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    department = db.query(DepartmentModel).get(department_id)
    if not department or department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@router.post("/", response_model=Department, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    department = DepartmentModel(**payload.dict(), admin_id=current_admin.id)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.put("/{department_id}", response_model=Department)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Department:
    department = db.query(DepartmentModel).get(department_id)
    if not department or department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    for field, value in payload.dict().items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)
    return department


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
