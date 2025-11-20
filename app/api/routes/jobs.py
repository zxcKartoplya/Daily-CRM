from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.job import Job, JobCreate, JobUpdate
from app.db.session import get_db
from app.models import Job as JobModel, Department as DepartmentModel, Admin as AdminModel


router = APIRouter()


def _ensure_department_access(department: DepartmentModel | None, current_admin: AdminModel) -> None:
    if not department or department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def _ensure_job_access(job: JobModel | None, current_admin: AdminModel) -> JobModel:
    if not job or job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/", response_model=List[Job])
def list_jobs(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Job]:
    return (
        db.query(JobModel)
        .join(JobModel.department)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .all()
    )


@router.get("/{job_id}", response_model=Job)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Job:
    job = db.query(JobModel).get(job_id)
    return _ensure_job_access(job, current_admin)


@router.post("/", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Job:
    department = db.query(DepartmentModel).get(payload.department_id)
    _ensure_department_access(department, current_admin)

    job = JobModel(**payload.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.put("/{job_id}", response_model=Job)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Job:
    job = db.query(JobModel).get(job_id)
    _ensure_job_access(job, current_admin)

    if payload.department_id != job.department_id:
        department = db.query(DepartmentModel).get(payload.department_id)
        _ensure_department_access(department, current_admin)

    for field, value in payload.dict().items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> None:
    job = db.query(JobModel).get(job_id)
    job = _ensure_job_access(job, current_admin)

    db.delete(job)
    db.commit()
