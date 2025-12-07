from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Statistic(Base):
    __tablename__ = "statistics"
    __table_args__ = (
        UniqueConstraint("date", "user_id", name="uq_statistics_date_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    value = Column(Integer, nullable=False)

    user = relationship("User", back_populates="statistics")
