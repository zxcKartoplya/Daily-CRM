from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    cost = Column(Integer, nullable=False)

    tasks = relationship("Task", back_populates="metric")
    statistics = relationship("Statistic", back_populates="metric")

