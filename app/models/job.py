from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("reviewers.id", ondelete="RESTRICT"), nullable=False)

    department = relationship("Department", back_populates="jobs")
    reviewer = relationship("Reviewer", back_populates="jobs")
    users = relationship("User", back_populates="job")
