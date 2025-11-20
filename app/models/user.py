from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)

    job = relationship("Job", back_populates="users")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    statistics = relationship("Statistic", back_populates="user", cascade="all, delete-orphan")

