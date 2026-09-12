from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import DailyEntryStatus, DayType


class DailyEntry(Base):
    __tablename__ = "daily_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_entries_user_date"),
        Index("ix_daily_entries_user_id_date", "user_id", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    day_type = Column(String, nullable=False, default=DayType.WORK.value)
    status = Column(String, nullable=False, default=DailyEntryStatus.DRAFT.value)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="daily_entries")
    department = relationship("Department", back_populates="daily_entries")
    items = relationship(
        "EntryItem",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryItem.position",
    )
