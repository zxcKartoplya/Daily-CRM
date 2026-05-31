from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class DailyReportTask(Base):
    __tablename__ = "daily_report_tasks"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    task_text = Column(String, nullable=True)
    slot = Column(String, nullable=False)

    daily_report = relationship("DailyReport", back_populates="tasks")
    task = relationship("Task")
