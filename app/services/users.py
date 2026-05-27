from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.schemas.user import User, UserDetail
from app.models import EmployeeProfile as EmployeeProfileModel
from app.models import EmployeeSettings as EmployeeSettingsModel
from app.models import User as UserModel
from app.models.enums import UserRole


def ensure_employee_profile(db: Session, user: UserModel) -> EmployeeProfileModel:
    if user.profile is None:
        user.profile = EmployeeProfileModel(
            position=user.job.name if user.job else None,
        )
        db.add(user.profile)
        db.flush()
    return user.profile


def ensure_employee_settings(db: Session, user: UserModel) -> EmployeeSettingsModel:
    if user.settings is None:
        user.settings = EmployeeSettingsModel()
        db.add(user.settings)
        db.flush()
    return user.settings


def ensure_employee_context(db: Session, user: UserModel) -> None:
    if user.role == UserRole.EMPLOYEE.value:
        ensure_employee_profile(db, user)
        ensure_employee_settings(db, user)


def serialize_user(user: UserModel) -> User:
    return User(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        status=user.status,
        job_id=user.job_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def serialize_user_detail(user: UserModel) -> UserDetail:
    return UserDetail(
        **serialize_user(user).model_dump(),
        profile=user.profile,
        settings=user.settings,
    )
