from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.schemas.metric import Metric, MetricCreate, MetricUpdate
from app.db.session import get_db
from app.models import Metric as MetricModel


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/", response_model=List[Metric])
def list_metrics(db: Session = Depends(get_db)) -> List[Metric]:
    return db.query(MetricModel).all()


@router.get("/{metric_id}", response_model=Metric)
def get_metric(metric_id: int, db: Session = Depends(get_db)) -> Metric:
    metric = db.query(MetricModel).get(metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return metric


@router.post("/", response_model=Metric, status_code=status.HTTP_201_CREATED)
def create_metric(payload: MetricCreate, db: Session = Depends(get_db)) -> Metric:
    metric = MetricModel(**payload.dict())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@router.put("/{metric_id}", response_model=Metric)
def update_metric(metric_id: int, payload: MetricUpdate, db: Session = Depends(get_db)) -> Metric:
    metric = db.query(MetricModel).get(metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    for field, value in payload.dict().items():
        setattr(metric, field, value)

    db.commit()
    db.refresh(metric)
    return metric


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric(metric_id: int, db: Session = Depends(get_db)) -> None:
    metric = db.query(MetricModel).get(metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    db.delete(metric)
    db.commit()
