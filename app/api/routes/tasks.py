from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.task import Task, TaskCreate, TaskUpdate
from app.db.session import get_db
from app.models import Task as TaskModel
from app.models import User as UserModel


router = APIRouter(dependencies=[Depends(require_admin_user)])


def _get_task_or_404(db: Session, task_id: int) -> TaskModel:
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _ensure_worker_exists(db: Session, user_id: int) -> None:
    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")


@router.get("", response_model=List[Task])
def list_tasks(
    user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Task]:
    query = db.query(TaskModel).order_by(TaskModel.date.desc())
    if user_id is not None:
        query = query.filter(TaskModel.user_id == user_id)
    return query.all()


@router.get("/{task_id}", response_model=Task)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    return _get_task_or_404(db, task_id)


@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
) -> Task:
    _ensure_worker_exists(db, payload.user_id)
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
) -> Task:
    task = _get_task_or_404(db, task_id)
    if payload.user_id != task.user_id:
        _ensure_worker_exists(db, payload.user_id)
    for field, value in payload.dict().items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> None:
    task = _get_task_or_404(db, task_id)
    db.delete(task)
    db.commit()
