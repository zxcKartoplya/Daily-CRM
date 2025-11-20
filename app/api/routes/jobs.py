from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.job import Job, JobCreate, JobUpdate
from app.db.session import get_db
from app.models import Job as JobModel


router = APIRouter()


@router.get("/", response_model=List[Job])
def list_jobs(db: Session = Depends(get_db)) -> List[Job]:
    return db.query(JobModel).all()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    job = db.query(JobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> Job:
    job = JobModel(**payload.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.put("/{job_id}", response_model=Job)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)) -> Job:
    job = db.query(JobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    for field, value in payload.dict().items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> None:
    job = db.query(JobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    db.delete(job)
    db.commit()

