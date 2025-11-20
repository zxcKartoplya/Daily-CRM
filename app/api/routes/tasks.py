from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.task import Task, TaskCreate, TaskUpdate
from app.db.session import get_db
from app.models import (
    Task as TaskModel,
    User as UserModel,
    Job as JobModel,
    Department as DepartmentModel,
    Admin as AdminModel,
)


router = APIRouter()


def _ensure_user_access(user: UserModel | None, current_admin: AdminModel) -> UserModel:
    if not user or user.job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _ensure_task_access(task: TaskModel | None, current_admin: AdminModel) -> TaskModel:
    if not task or task.user.job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/", response_model=List[Task])
def list_tasks(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Task]:
    return (
        db.query(TaskModel)
        .join(TaskModel.user)
        .join(UserModel.job)
        .join(JobModel.department)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .all()
    )


@router.get("/{task_id}", response_model=Task)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Task:
    task = db.query(TaskModel).get(task_id)
    return _ensure_task_access(task, current_admin)


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Task:
    user = db.query(UserModel).get(payload.user_id)
    _ensure_user_access(user, current_admin)

    task = TaskModel(**payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Task:
    task = db.query(TaskModel).get(task_id)
    task = _ensure_task_access(task, current_admin)

    if payload.user_id != task.user_id:
        user = db.query(UserModel).get(payload.user_id)
        _ensure_user_access(user, current_admin)

    for field, value in payload.dict().items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> None:
    task = db.query(TaskModel).get(task_id)
    task = _ensure_task_access(task, current_admin)

    db.delete(task)
    db.commit()
