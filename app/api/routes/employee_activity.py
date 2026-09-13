from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.activity import EmployeeActivity
from app.db.session import get_db
from app.models import User as UserModel
from app.models.enums import ActivityPeriod
from app.services.employee_activity import calculate_employee_activity


router = APIRouter()


@router.get("", response_model=EmployeeActivity)
def get_employee_activity(
    period: ActivityPeriod = Query(default=ActivityPeriod.WEEK),
    day: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeActivity:
    return calculate_employee_activity(db, current_user.id, period, day)
