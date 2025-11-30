from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.schemas.admin import AdminLoginRequest, TokenResponse
from app.core.security import verify_password, create_access_token
from app.db.session import get_db
from app.models import Admin as AdminModel


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: AdminLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    admin = db.query(AdminModel).filter(AdminModel.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Неверный email или пароль"},
        )

    token = create_access_token(admin_id=admin.id, email=admin.email)
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"message": "Login successful", "access_token": token, "success": True})
