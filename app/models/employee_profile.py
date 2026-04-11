from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    position = Column(String, nullable=True)
    avatar = Column(String, nullable=True)
    timezone = Column(String, nullable=True)
    preferred_language = Column(String, nullable=True)

    user = relationship("User", back_populates="profile")
