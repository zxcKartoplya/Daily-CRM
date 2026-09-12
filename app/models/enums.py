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


class DayType(str, Enum):
    WORK = "work"
    OFF = "off"


class DailyEntryStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class EntryItemStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    DROPPED = "dropped"


OPEN_ITEM_STATUSES: frozenset[str] = frozenset(
    {EntryItemStatus.IN_PROGRESS.value, EntryItemStatus.BLOCKED.value}
)
CLOSED_ITEM_STATUSES: frozenset[str] = frozenset(
    {EntryItemStatus.DONE.value, EntryItemStatus.DROPPED.value}
)
