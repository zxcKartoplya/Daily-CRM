from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"


class UserAccessStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ScheduleType(str, Enum):
    WEEKLY = "weekly"
    NONE = "none"


DEFAULT_WORK_DAYS: list[int] = [1, 2, 3, 4, 5]


class DayType(str, Enum):
    WORK = "work"
    OFF = "off"


class OffReason(str, Enum):
    VACATION = "vacation"
    SICK_LEAVE = "sick_leave"
    UNPAID_LEAVE = "unpaid_leave"
    BUSINESS_TRIP = "business_trip"
    OTHER = "other"


OFF_REASON_LABELS: dict[OffReason, str] = {
    OffReason.VACATION: "Отпуск",
    OffReason.SICK_LEAVE: "Больничный",
    OffReason.UNPAID_LEAVE: "Отгул за свой счёт",
    OffReason.BUSINESS_TRIP: "Командировка",
    OffReason.OTHER: "Другое",
}


def off_reason_requires_note(reason: OffReason) -> bool:
    return reason is OffReason.OTHER


class DailyEntryStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class DayState(str, Enum):
    SUBMITTED = "submitted"
    DRAFT = "draft"
    MISSING = "missing"
    OFF = "off"
    REST = "rest"


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


class ActivityPeriod(str, Enum):
    WEEK = "week"
    MONTH = "month"


class ChainOutcome(str, Enum):
    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"
