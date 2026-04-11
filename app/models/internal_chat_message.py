from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class InternalChatMessage(Base):
    __tablename__ = "internal_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_to_daily_report = Column(Boolean, nullable=False, default=False)
    daily_report_id = Column(Integer, ForeignKey("daily_reports.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="internal_chat_messages")
    daily_report = relationship("DailyReport", back_populates="internal_chat_messages")
