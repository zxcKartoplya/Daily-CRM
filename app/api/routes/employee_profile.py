from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.employee_profile import EmployeeProfile, EmployeeProfileUpdate
from app.db.session import get_db
from app.models import User as UserModel
from app.services.users import ensure_employee_profile


router = APIRouter()


@router.get("", response_model=EmployeeProfile)
def get_employee_profile(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeProfile:
    profile = ensure_employee_profile(db, current_user)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("", response_model=EmployeeProfile)
def update_employee_profile(
    payload: EmployeeProfileUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeProfile:
    profile = ensure_employee_profile(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
