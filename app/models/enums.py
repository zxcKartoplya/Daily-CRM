from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"


class ScheduleType(str, Enum):
    WEEKLY = "weekly"
    NONE = "none"


DEFAULT_WORK_DAYS: list[int] = [1, 2, 3, 4, 5]


class DailyReportSource(str, Enum):
    INTERNAL_WEB = "internal_web"
    TELEGRAM = "telegram"
    SLACK = "slack"
    EMAIL = "email"
    API = "api"


class DailyReportStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IMPORTED = "imported"


class BlockerType(str, Enum):
    TECHNICAL = "technical"
    PROCESS = "process"
    EXTERNAL = "external"
    PERSONAL = "personal"
    OTHER = "other"


class DailyReportTaskSlot(str, Enum):
    DONE = "done"
    PLANNED = "planned"
