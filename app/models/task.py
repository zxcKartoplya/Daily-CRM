from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="tasks")
    metric = relationship("Metric", back_populates="tasks")

