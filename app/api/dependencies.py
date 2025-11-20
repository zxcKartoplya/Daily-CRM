from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Admin as AdminModel


def _get_admin_by_id(admin_id: int, db: Session) -> AdminModel:
    admin = db.query(AdminModel).get(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin not found")
    return admin


def require_admin(
    admin_id_header: str | None = Header(None, alias="X-Admin-Id"),
    db: Session = Depends(get_db),
) -> AdminModel:
    if admin_id_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Admin-Id header is required",
        )

    try:
        admin_id = int(admin_id_header)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid admin id") from exc

    return _get_admin_by_id(admin_id, db)


def optional_admin(
    admin_id_header: str | None = Header(None, alias="X-Admin-Id"),
    db: Session = Depends(get_db),
) -> AdminModel | None:
    if admin_id_header is None:
        return None

    try:
        admin_id = int(admin_id_header)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid admin id") from exc

    return _get_admin_by_id(admin_id, db)

