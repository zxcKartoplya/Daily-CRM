from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_password, decode_access_token
from app.db.session import get_db
from app.models import Admin as AdminModel


def _get_admin_by_id(admin_id: int, db: Session) -> AdminModel:
    admin = db.query(AdminModel).get(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin not found")
    return admin


def _resolve_admin_from_token(token: str, db: Session) -> AdminModel:
    try:
        payload = decode_access_token(token)
        admin_id = int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from exc

    return _get_admin_by_id(admin_id, db)


def require_admin(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> AdminModel:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization header with Bearer token is required",
        )
    token = authorization.split(" ", 1)[1]
    return _resolve_admin_from_token(token, db)


def optional_admin(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> AdminModel | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return _resolve_admin_from_token(token, db)
