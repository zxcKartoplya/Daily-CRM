from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.worker import Worker, WorkerCreate, WorkerDetail, WorkerUpdate
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Department as DepartmentModel
from app.models import Job as JobModel
from app.models import User as UserModel
from app.models.enums import UserRole
from app.services.users import ensure_employee_context, serialize_user_detail


router = APIRouter(dependencies=[Depends(require_admin_user)])


def _get_worker_or_404(db: Session, worker_id: int) -> UserModel:
    user = (
        db.query(UserModel)
        .options(
            joinedload(UserModel.department),
            joinedload(UserModel.profile),
            joinedload(UserModel.settings),
        )
        .filter(UserModel.id == worker_id, UserModel.role == UserRole.EMPLOYEE.value)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return user


def _ensure_department(db: Session, department_id: int | None) -> None:
    if department_id is None:
        return
    if not db.get(DepartmentModel, department_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def _ensure_job(db: Session, job_id: int | None) -> None:
    if job_id is None:
        return
    if not db.get(JobModel, job_id):
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


def _serialize_worker(user: UserModel) -> Worker:
    return Worker(
        id=user.id,
        name=user.name,
        email=user.email,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        job_id=user.job_id,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=List[Worker])
def list_workers(
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Worker]:
    query = (
        db.query(UserModel)
        .options(joinedload(UserModel.department))
        .filter(UserModel.role == UserRole.EMPLOYEE.value)
        .order_by(UserModel.created_at.desc())
    )
    if department_id is not None:
        query = query.filter(UserModel.department_id == department_id)
    return [_serialize_worker(user) for user in query.all()]


@router.get("/{worker_id}", response_model=WorkerDetail)
def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    user = _get_worker_or_404(db, worker_id)
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.dict())


@router.post("", response_model=WorkerDetail, status_code=status.HTTP_201_CREATED)
def create_worker(
    payload: WorkerCreate,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    if payload.email:
        if db.query(UserModel).filter(UserModel.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

    _ensure_department(db, payload.department_id)
    _ensure_job(db, payload.job_id)
    _validate_job_department(db, payload.job_id, payload.department_id)

    user = UserModel(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password) if payload.password else None,
        role=UserRole.EMPLOYEE.value,
        department_id=payload.department_id,
        job_id=payload.job_id,
        status=payload.status.value,
    )
    db.add(user)
    db.flush()
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.dict())


@router.put("/{worker_id}", response_model=WorkerDetail)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    user = _get_worker_or_404(db, worker_id)
    update_data = payload.dict(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        duplicate = (
            db.query(UserModel)
            .filter(UserModel.email == update_data["email"], UserModel.id != user.id)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

    if "department_id" in update_data:
        _ensure_department(db, update_data["department_id"])
    if "job_id" in update_data:
        _ensure_job(db, update_data["job_id"])

    new_job_id = update_data.get("job_id", user.job_id)
    new_dept_id = update_data.get("department_id", user.department_id)
    _validate_job_department(db, new_job_id, new_dept_id)

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
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.dict())


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
) -> None:
    user = _get_worker_or_404(db, worker_id)
    db.delete(user)
    db.commit()
