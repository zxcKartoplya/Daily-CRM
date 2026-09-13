from pydantic import BaseModel

from app.models.enums import OffReason


class OffReasonOption(BaseModel):
    code: OffReason
    label: str
    requires_note: bool
