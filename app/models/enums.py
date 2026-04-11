from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"


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
