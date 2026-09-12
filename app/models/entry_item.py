from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class EntryItem(Base):
    __tablename__ = "entry_items"
    __table_args__ = (
        UniqueConstraint("chain_id", "entry_id", name="uq_entry_items_chain_id_entry_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("daily_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(String(36), nullable=False, index=True, default=lambda: str(uuid4()))
    text = Column(Text, nullable=True)
    status = Column(String, nullable=False, index=True)
    link = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    entry = relationship("DailyEntry", back_populates="items")
