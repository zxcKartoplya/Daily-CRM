from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Statistic(Base):
    __tablename__ = "statistics"
    __table_args__ = (
        UniqueConstraint("date", "user_id", "metric_id", name="uq_statistics_date_user_metric"),
    )

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    value = Column(Integer, nullable=False)

    user = relationship("User", back_populates="statistics")
    metric = relationship("Metric", back_populates="statistics")

