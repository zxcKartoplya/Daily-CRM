from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import DailyReportSource, DailyReportStatus


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_report_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    source = Column(String, nullable=False, default=DailyReportSource.INTERNAL_WEB.value)
    status = Column(String, nullable=False, default=DailyReportStatus.SUBMITTED.value)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    report_date = Column(Date, nullable=False, index=True)
    yesterday_text = Column(Text, nullable=True)
    today_text = Column(Text, nullable=True)
    blockers_text = Column(Text, nullable=True)
    mood = Column(String, nullable=True)
    self_rating = Column(Integer, nullable=True)
    needs_help = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="daily_reports")
    department = relationship("Department", back_populates="daily_reports")
    internal_chat_messages = relationship("InternalChatMessage", back_populates="daily_report")
