from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import DEFAULT_WORK_DAYS, ScheduleType, UserRole, UserStatus


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, nullable=False, default=UserRole.EMPLOYEE.value)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=False, default=UserStatus.ACTIVE.value)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    schedule_type = Column(String, nullable=False, default=ScheduleType.WEEKLY.value)
    work_days = Column(JSON, nullable=True, default=lambda: list(DEFAULT_WORK_DAYS))

    department = relationship("Department", back_populates="users")
    job = relationship("Job", back_populates="users")
    profile = relationship("EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    settings = relationship("EmployeeSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    daily_entries = relationship("DailyEntry", back_populates="user", cascade="all, delete-orphan")
    internal_chat_messages = relationship(
        "InternalChatMessage",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    assessments = relationship(
        "Assessment",
        foreign_keys="Assessment.worker_id",
        back_populates="worker",
        cascade="all, delete-orphan",
    )
    statistics = relationship("Statistic", back_populates="user", cascade="all, delete-orphan")
