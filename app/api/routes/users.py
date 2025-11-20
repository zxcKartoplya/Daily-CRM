from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.user import User, UserCreate, UserUpdate
from app.db.session import get_db
from app.models import (
    User as UserModel,
    Job as JobModel,
    Department as DepartmentModel,
    Admin as AdminModel,
)


router = APIRouter()


def _ensure_job_access(job: JobModel | None, current_admin: AdminModel) -> JobModel:
    if not job or job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _ensure_user_access(user: UserModel | None, current_admin: AdminModel) -> UserModel:
    if not user or user.job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/", response_model=List[User])
def list_users(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[User]:
    return (
        db.query(UserModel)
        .join(UserModel.job)
        .join(JobModel.department)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .all()
    )


@router.get("/{user_id}", response_model=User)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> User:
    user = db.query(UserModel).get(user_id)
    return _ensure_user_access(user, current_admin)


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> User:
    job = db.query(JobModel).get(payload.job_id)
    _ensure_job_access(job, current_admin)

    user = UserModel(**payload.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=User)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> User:
    user = db.query(UserModel).get(user_id)
    user = _ensure_user_access(user, current_admin)

    if payload.job_id != user.job_id:
        job = db.query(JobModel).get(payload.job_id)
        _ensure_job_access(job, current_admin)

    for field, value in payload.dict().items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> None:
    user = db.query(UserModel).get(user_id)
    user = _ensure_user_access(user, current_admin)

    db.delete(user)
    db.commit()
