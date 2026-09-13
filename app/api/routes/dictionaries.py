from typing import List

from fastapi import APIRouter, Depends

from app.api.dependencies import require_current_user
from app.api.schemas.dictionary import OffReasonOption
from app.models import User as UserModel
from app.models.enums import OFF_REASON_LABELS, OffReason, off_reason_requires_note

router = APIRouter()


@router.get("/off-reasons", response_model=List[OffReasonOption])
def list_off_reasons(_: UserModel = Depends(require_current_user)) -> List[OffReasonOption]:
    return [
        OffReasonOption(
            code=reason,
            label=OFF_REASON_LABELS[reason],
            requires_note=off_reason_requires_note(reason),
        )
        for reason in OffReason
    ]
