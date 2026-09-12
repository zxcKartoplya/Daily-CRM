from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_user
from app.api.schemas.internal_chat import InternalChatMessage, InternalChatMessageCreate
from app.db.session import get_db
from app.models import InternalChatMessage as InternalChatMessageModel
from app.models import User as UserModel


router = APIRouter()


@router.get("/messages", response_model=List[InternalChatMessage])
def list_internal_chat_messages(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> List[InternalChatMessage]:
    return (
        db.query(InternalChatMessageModel)
        .filter(InternalChatMessageModel.user_id == current_user.id)
        .order_by(InternalChatMessageModel.created_at.desc())
        .all()
    )


@router.post("/messages", response_model=InternalChatMessage, status_code=status.HTTP_201_CREATED)
def create_internal_chat_message(
    payload: InternalChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_employee_user),
) -> InternalChatMessage:
    message = InternalChatMessageModel(
        user_id=current_user.id,
        message_text=payload.message_text,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
