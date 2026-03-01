from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin
from app.api.schemas.job import Job, JobCreate, JobUpdate
from app.db.session import get_db
from app.models import (
    Job as JobModel,
    Department as DepartmentModel,
    Admin as AdminModel,
    Reviewer as ReviewerModel,
)


router = APIRouter()


def _to_job_response(job: JobModel) -> Job:
    return Job(
        id=job.id,
        name=job.name,
        description=job.description,
        department_id=job.department_id,
        department_name=job.department.name if job.department else None,
        reviewer_id=job.reviewer_id,
        reviewer_name=job.reviewer.name if job.reviewer else None,
    )


def _ensure_department_access(department: DepartmentModel | None, current_admin: AdminModel) -> None:
    if not department or department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def _ensure_job_access(job: JobModel | None, current_admin: AdminModel) -> JobModel:
    if not job or job.department.admin_id != current_admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _resolve_reviewer_id(db: Session, reviewer_id: int | None) -> int | None:
    if reviewer_id is None:
        return None

    reviewer = db.get(ReviewerModel, reviewer_id)
    if reviewer:
        return reviewer.id

    # Frontend compatibility: some forms send 1-based index instead of DB id.
    reviewer_ids = [row[0] for row in db.query(ReviewerModel.id).order_by(ReviewerModel.id).all()]
    if 1 <= reviewer_id <= len(reviewer_ids):
        return reviewer_ids[reviewer_id - 1]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Reviewer not found. Available reviewer ids: {reviewer_ids}",
    )


@router.get("", response_model=List[Job])
def list_jobs(
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> List[Job]:
    jobs = (
        db.query(JobModel)
        .options(joinedload(JobModel.department), joinedload(JobModel.reviewer))
        .join(JobModel.department)
        .filter(DepartmentModel.admin_id == current_admin.id)
        .all()
    )
    return [_to_job_response(job) for job in jobs]


@router.get("/{job_id}", response_model=Job)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Job:
    job = db.query(JobModel).options(joinedload(JobModel.department), joinedload(JobModel.reviewer)).get(job_id)
    job = _ensure_job_access(job, current_admin)
    return _to_job_response(job)


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(require_admin),
) -> Job:
    department = db.query(DepartmentModel).get(payload.department_id)
    _ensure_department_access(department, current_admin)
    reviewer_id = _resolve_reviewer_id(db, payload.reviewer_id)

    job_data = payload.dict()
    job_data["reviewer_id"] = reviewer_id
    job = JobModel(**job_data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_job_response(job)


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
    reviewer_id = _resolve_reviewer_id(db, payload.reviewer_id)

    update_data = payload.dict()
    update_data["reviewer_id"] = reviewer_id
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return _to_job_response(job)


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
