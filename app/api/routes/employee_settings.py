from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.employee_settings import EmployeeSettings, EmployeeSettingsUpdate
from app.db.session import get_db
from app.models import User as UserModel
from app.services.users import ensure_employee_settings


router = APIRouter()


@router.get("", response_model=EmployeeSettings)
def get_employee_settings(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeSettings:
    settings = ensure_employee_settings(db, current_user)
    db.commit()
    db.refresh(settings)
    return settings


@router.put("", response_model=EmployeeSettings)
def update_employee_settings(
    payload: EmployeeSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> EmployeeSettings:
    settings = ensure_employee_settings(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
