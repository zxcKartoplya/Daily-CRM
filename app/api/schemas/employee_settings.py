from datetime import time

from pydantic import BaseModel


class EmployeeSettingsBase(BaseModel):
    notification_time: time | None = None
    reminder_enabled: bool = True
    daily_template_id: str | None = None
    preferred_daily_format: str | None = None


class EmployeeSettingsUpdate(EmployeeSettingsBase):
    pass


class EmployeeSettings(EmployeeSettingsBase):
    user_id: int

    class Config:
        from_attributes = True
