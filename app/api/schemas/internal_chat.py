from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InternalChatMessageCreate(BaseModel):
    message_text: str


class InternalChatMessage(BaseModel):
    id: int
    user_id: int
    message_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
