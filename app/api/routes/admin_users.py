from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.user import User, UserCreate, UserDetail, UserUpdate
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Department as DepartmentModel
from app.models import Job as JobModel
from app.models import User as UserModel
from app.models.enums import UserRole
from app.services.users import ensure_employee_context, serialize_user, serialize_user_detail


router = APIRouter()


def _get_user_or_404(db: Session, user_id: int) -> UserModel:
    user = (
        db.query(UserModel)
        .options(
            joinedload(UserModel.department),
            joinedload(UserModel.profile),
            joinedload(UserModel.settings),
        )
        .filter(UserModel.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _ensure_department(db: Session, department_id: int | None) -> None:
    if department_id is None:
        return
    department = db.get(DepartmentModel, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def _ensure_job(db: Session, job_id: int | None) -> None:
    if job_id is None:
        return
    job = db.get(JobModel, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


def _validate_job_department(db: Session, job_id: int | None, department_id: int | None) -> None:
    if job_id is None or department_id is None:
        return
    job = db.get(JobModel, job_id)
    if job and job.department_id != department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job does not belong to the specified department",
        )


@router.get("", response_model=List[User])
def list_admin_users(
    role: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[User]:
    query = db.query(UserModel).options(joinedload(UserModel.department)).order_by(UserModel.created_at.desc())
    if role:
        query = query.filter(UserModel.role == role)
    if department_id is not None:
        query = query.filter(UserModel.department_id == department_id)
    return [serialize_user(user) for user in query.all()]


@router.get("/{user_id}", response_model=UserDetail)
def get_admin_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> UserDetail:
    user = _get_user_or_404(db, user_id)
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    return serialize_user_detail(user)


@router.post("", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> UserDetail:
    if payload.email:
        existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    _ensure_department(db, payload.department_id)
    _ensure_job(db, payload.job_id)
    _validate_job_department(db, payload.job_id, payload.department_id)

    user = UserModel(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password) if payload.password else None,
        role=payload.role.value,
        department_id=payload.department_id,
        status=payload.status.value,
        job_id=payload.job_id,
    )
    db.add(user)
    db.flush()
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    return serialize_user_detail(user)


@router.put("/{user_id}", response_model=UserDetail)
def update_admin_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(require_admin_user),
) -> UserDetail:
    user = _get_user_or_404(db, user_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        duplicate = (
            db.query(UserModel)
            .filter(UserModel.email == update_data["email"], UserModel.id != user.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    if "department_id" in update_data:
        _ensure_department(db, update_data["department_id"])
    if "job_id" in update_data:
        _ensure_job(db, update_data["job_id"])

    new_job_id = update_data.get("job_id", user.job_id)
    new_dept_id = update_data.get("department_id", user.department_id)
    _validate_job_department(db, new_job_id, new_dept_id)

    if "role" in update_data and update_data["role"] is not None:
        update_data["role"] = update_data["role"].value
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value
    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            user.password_hash = hash_password(password)

    for field, value in update_data.items():
        setattr(user, field, value)

    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    return serialize_user_detail(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(require_admin_user),
) -> None:
    user = _get_user_or_404(db, user_id)
    if user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete current admin")

    if user.role == UserRole.ADMIN.value:
        admin_count = db.query(UserModel).filter(UserModel.role == UserRole.ADMIN.value).count()
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last admin")

    db.delete(user)
    db.commit()
