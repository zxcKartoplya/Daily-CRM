from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class Reviewer(Base):
    __tablename__ = "reviewers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    metrics = Column(JSON, nullable=True)

    jobs = relationship("Job", back_populates="reviewer")
