from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import optional_admin, require_admin
from app.api.schemas.admin import Admin, AdminCreate, AdminUpdate
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Admin as AdminModel


router = APIRouter()


@router.get("", response_model=List[Admin])
def list_admins(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
) -> List[Admin]:
    return db.query(AdminModel).all()


@router.get("/{admin_id}", response_model=Admin)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
) -> Admin:
    admin = db.query(AdminModel).get(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    return admin


@router.post("", response_model=Admin, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(optional_admin),
) -> Admin:
    existing = db.query(AdminModel).filter(AdminModel.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin with this email already exists")

    total_admins = db.query(AdminModel).count()
    if total_admins > 0 and current_admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin credentials required")

    admin = AdminModel(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@router.put("/{admin_id}", response_model=Admin)
def update_admin(
    admin_id: int,
    payload: AdminUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
) -> Admin:
    admin = db.query(AdminModel).get(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    update_data = payload.dict(exclude_unset=True)
    if "full_name" in update_data and update_data["full_name"] is not None:
        admin.full_name = update_data["full_name"]
    if "password" in update_data and update_data["password"]:
        admin.password_hash = hash_password(update_data["password"])

    db.commit()
    db.refresh(admin)
    return admin


@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
) -> None:
    admin = db.query(AdminModel).get(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if admin.departments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin with assigned departments",
        )

    db.delete(admin)
    db.commit()
