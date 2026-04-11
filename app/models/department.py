from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="RESTRICT"), nullable=True)

    jobs = relationship("Job", back_populates="department", cascade="all, delete-orphan")
    users = relationship("User", back_populates="department")
    daily_reports = relationship("DailyReport", back_populates="department")
    admin = relationship("Admin", back_populates="departments")
