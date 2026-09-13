from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("reviewers.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    model = Column(String, nullable=False)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    feedback_text = Column(Text, nullable=False)
    metrics_snapshot = Column(JSON, nullable=False, default=list)

    worker = relationship("User", foreign_keys=[worker_id], back_populates="assessments")
    author = relationship("User", foreign_keys=[created_by])
    reviewer = relationship("Reviewer")
    job = relationship("Job")
