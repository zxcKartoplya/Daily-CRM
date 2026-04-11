from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_current_user
from app.api.schemas.auth import BootstrapAdminRequest, LoginRequest, TokenResponse
from app.api.schemas.user import User
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User as UserModel
from app.models.enums import UserRole, UserStatus
from app.services.users import ensure_employee_context, serialize_user


router = APIRouter()


@router.post("/bootstrap-admin", response_model=User, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminRequest, db: Session = Depends(get_db)) -> User:
    existing_admin = db.query(UserModel).filter(UserModel.role == UserRole.ADMIN.value).first()
    if existing_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin already exists")

    existing_email = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    admin = UserModel(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return serialize_user(admin)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or password")
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not active")

    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.get("/me", response_model=User)
def me(current_user: UserModel = Depends(require_current_user)) -> User:
    return serialize_user(current_user)
