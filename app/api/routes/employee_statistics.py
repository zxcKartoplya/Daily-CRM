from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.analytics import EmployeeStatistics
from app.db.session import get_db
from app.models import User as UserModel
from app.services.employee_statistics import calculate_employee_statistics


router = APIRouter()


@router.get("", response_model=EmployeeStatistics)
def get_employee_statistics(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeStatistics:
    return calculate_employee_statistics(db, current_user.id)
