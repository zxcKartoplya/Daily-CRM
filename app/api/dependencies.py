from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User as UserModel
from app.models.enums import UserRole, UserStatus


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required",
        )
    return authorization.split(" ", 1)[1]


def _get_user_by_id(user_id: int, db: Session) -> UserModel:
    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _resolve_user_from_token(token: str, db: Session) -> UserModel:
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = _get_user_by_id(user_id, db)
    if user.status == UserStatus.INACTIVE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    return user


def require_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserModel:
    token = _extract_bearer_token(authorization)
    return _resolve_user_from_token(token, db)


def require_admin_user(current_user: UserModel = Depends(require_current_user)) -> UserModel:
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_employee_user(current_user: UserModel = Depends(require_current_user)) -> UserModel:
    if current_user.role != UserRole.EMPLOYEE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee access required")
    return current_user


def optional_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserModel | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return _resolve_user_from_token(token, db)


def optional_admin(
    current_user: UserModel | None = Depends(optional_current_user),
) -> UserModel | None:
    if current_user is None:
        return None
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_admin(current_user: UserModel = Depends(require_admin_user)) -> UserModel:
    return current_user
