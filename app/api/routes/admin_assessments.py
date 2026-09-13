from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.assessment import Assessment
from app.db.session import get_db
from app.services.assessments import get_assessment, serialize_assessment


router = APIRouter(dependencies=[Depends(require_admin_user)])


@router.get("/{assessment_id}", response_model=Assessment)
def get_assessment_by_id(assessment_id: int, db: Session = Depends(get_db)) -> Assessment:
    assessment = get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return serialize_assessment(assessment)
