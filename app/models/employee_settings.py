from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Time
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmployeeSettings(Base):
    __tablename__ = "employee_settings"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notification_time = Column(Time, nullable=True)
    reminder_enabled = Column(Boolean, nullable=False, default=True)
    daily_template_id = Column(String, nullable=True)
    preferred_daily_format = Column(String, nullable=True)

    user = relationship("User", back_populates="settings")
