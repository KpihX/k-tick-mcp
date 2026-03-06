"""
Pydantic v2 models for the TickTick API (V1 Official + V2 Unofficial).

Design principles:
  - extra="ignore"       : unknown API fields silently dropped (forward-compatibility)
  - All API fields optional: the API omits fields when empty
  - Helper builders for complex formats (TRIGGER, RRULE) so callers never hand-craft strings

Covers: Tasks, Projects, Columns, Tags, Habits, HabitCheckins, ProjectGroups/Folders,
        Focus stats, User/Profile, Productivity stats, Batch payloads.

References:
  - https://developer.ticktick.com/api
  - https://lazeroffmichael.github.io/ticktick-py/usage/tasks/
  - https://github.com/gritse/TickTickSharp
  - https://github.com/dev-mirzabicer/ticktick-sdk (V2 internals)
"""
from __future__ import annotations

from enum import IntEnum, Enum
from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class Priority(IntEnum):
    NONE   = 0
    LOW    = 1
    MEDIUM = 3
    HIGH   = 5

    @classmethod
    def label(cls, value: int) -> str:
        return {0: "none", 1: "low", 3: "medium", 5: "high"}.get(value, str(value))


class TaskStatus(IntEnum):
    """Task-level status codes."""
    NORMAL    = 0
    COMPLETED = 2
    ABANDONED = -1   # V2 only — "won't do"


class ChecklistStatus(IntEnum):
    """Subtask/checklist item status. Different from TaskStatus (0/1 not 0/2)."""
    NORMAL    = 0
    COMPLETED = 1


class TaskKind(str, Enum):
    TEXT      = "TEXT"
    NOTE      = "NOTE"
    CHECKLIST = "CHECKLIST"


class ProjectKind(str, Enum):
    TASK = "TASK"
    NOTE = "NOTE"


class ProjectViewMode(str, Enum):
    LIST     = "list"
    KANBAN   = "kanban"
    TIMELINE = "timeline"


class HabitType(str, Enum):
    BOOLEAN = "Boolean"
    REAL    = "Real"


class HabitStatus(IntEnum):
    ACTIVE   = 0
    ARCHIVED = 2


class TagSortType(str, Enum):
    PROJECT   = "project"
    DUE_DATE  = "dueDate"
    TITLE     = "title"
    PRIORITY  = "priority"


# ═══════════════════════════════════════════════════════════════════════════════
#  iCalendar Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def build_reminder_trigger(minutes_before: int) -> str:
    """
    Convert an offset in minutes into an iCalendar TRIGGER string.

    Args:
        minutes_before: How many minutes before the due date to fire the reminder.
            0  → at due time  → "TRIGGER:PT0S"
            30 → 30 min before → "TRIGGER:-PT30M"
            60 → 1 hour before → "TRIGGER:-PT1H"
         1440 → 1 day before  → "TRIGGER:-P1D"
         2880 → 2 days before  → "TRIGGER:-P2D"
    """
    if minutes_before == 0:
        return "TRIGGER:PT0S"

    total = abs(minutes_before)
    days = total // 1440
    remaining = total % 1440
    hours = remaining // 60
    mins = remaining % 60

    period = "P"
    if days:
        period += f"{days}D"

    time_part = ""
    if hours or mins:
        time_part = "T"
        if hours:
            time_part += f"{hours}H"
        if mins:
            time_part += f"{mins}M"

    return f"TRIGGER:-{period}{time_part}"


def build_rrule(
    frequency: str,
    interval: int = 1,
    by_day: Optional[list[str]] = None,
    by_month_day: Optional[int] = None,
    by_month: Optional[int] = None,
    count: Optional[int] = None,
    until: Optional[str] = None,
    tt_times: Optional[int] = None,
) -> str:
    """
    Build an iCalendar RRULE string for recurring tasks or habits.

    Args:
        frequency: "DAILY" | "WEEKLY" | "MONTHLY" | "YEARLY"
        interval: Repeat every N units (default 1).
        by_day: Weekday codes ["MO","TU","WE","TH","FR","SA","SU"].
        by_month_day: Day of the month (1-31) for MONTHLY recurrence.
        by_month: Month number (1-12) for YEARLY recurrence.
        count: End after N occurrences.
        until: End date in UTC format "20251231T000000Z".
        tt_times: TickTick-specific "X times per week" (e.g., 5 = do 5x/week).

    Examples:
        build_rrule("DAILY")                                → "RRULE:FREQ=DAILY"
        build_rrule("WEEKLY", by_day=["MO","WE","FR"])      → "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"
        build_rrule("MONTHLY", by_month_day=15)             → "RRULE:FREQ=MONTHLY;BYMONTHDAY=15"
        build_rrule("WEEKLY", tt_times=5)                   → "RRULE:FREQ=WEEKLY;TT_TIMES=5"
    """
    freq = frequency.upper()
    parts = [f"RRULE:FREQ={freq}"]
    if interval > 1:
        parts.append(f"INTERVAL={interval}")
    if by_day:
        parts.append(f"BYDAY={','.join(d.upper() for d in by_day)}")
    if by_month_day:
        parts.append(f"BYMONTHDAY={by_month_day}")
    if by_month:
        parts.append(f"BYMONTH={by_month}")
    if count:
        parts.append(f"COUNT={count}")
    if until:
        parts.append(f"UNTIL={until}")
    if tt_times:
        parts.append(f"TT_TIMES={tt_times}")
    return ";".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
#  Sub-models
# ═══════════════════════════════════════════════════════════════════════════════

class ChecklistItem(BaseModel):
    """A subtask / checklist item within a task.  status uses 0/1 (not 0/2)."""
    model_config = ConfigDict(extra="ignore")

    id:            Optional[str]  = None
    title:         str            = ""
    status:        int            = ChecklistStatus.NORMAL
    completedTime: Optional[str]  = None
    isAllDay:      Optional[bool] = None
    sortOrder:     Optional[int]  = None
    startDate:     Optional[str]  = None
    timeZone:      Optional[str]  = None

    @field_validator("completedTime", mode="before")
    @classmethod
    def _coerce_completed_time(cls, v: Any) -> str | None:
        """API may send epoch-ms int instead of ISO string."""
        if v is None:
            return None
        return str(v)

    def is_completed(self) -> bool:
        return self.status == ChecklistStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
#  Core Models
# ═══════════════════════════════════════════════════════════════════════════════

class Task(BaseModel):
    """
    Full TickTick task model — covers both V1 and V2 API fields.

    Key date format: "yyyy-MM-dd'T'HH:mm:ssZ"  e.g. "2025-06-01T09:00:00+0000"
    Key reminder format: iCalendar TRIGGER       e.g. "TRIGGER:-PT30M"
    Key repeat format: iCalendar RRULE           e.g. "RRULE:FREQ=DAILY;INTERVAL=1"
    """
    model_config = ConfigDict(extra="ignore")

    # Identity
    id:            Optional[str] = None
    projectId:     Optional[str] = None

    # Content
    title:         str                 = ""
    content:       Optional[str]       = None
    desc:          Optional[str]       = None

    # Kind
    kind:          Optional[str]       = None   # "TEXT" | "NOTE" | "CHECKLIST"

    # Dates
    allDay:        Optional[bool]      = None
    isAllDay:      Optional[bool]      = None   # V2 variant
    startDate:     Optional[str]       = None
    dueDate:       Optional[str]       = None
    timeZone:      Optional[str]       = None
    completedTime: Optional[str]       = None
    isFloating:    Optional[bool]      = None

    # Recurrence & reminders
    reminders:     list               = Field(default_factory=list)
    repeat:        Optional[str]       = None   # V1 alias
    repeatFlag:    Optional[str]       = None   # V2 name
    repeatFrom:    Optional[int]       = None

    @field_validator("repeatFrom", mode="before")
    @classmethod
    def _coerce_repeat_from(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)

    # Priority & status
    priority:      int                 = Priority.NONE
    status:        int                 = TaskStatus.NORMAL

    # Organization
    sortOrder:     Optional[int]       = None
    tags:          list[str]           = Field(default_factory=list)

    # Subtasks / checklist
    items:         list[ChecklistItem] = Field(default_factory=list)

    # V2 hierarchy
    parentId:      Optional[str]       = None
    childIds:      list[str]           = Field(default_factory=list)

    # V2 Kanban
    columnId:      Optional[str]       = None

    # V2 Pin
    pinnedTime:    Optional[str]       = None

    # V2 Progress
    progress:      Optional[int]       = None

    # V2 Focus
    focusSummaries: list              = Field(default_factory=list)

    # V2 Soft delete
    deleted:       Optional[int]       = None

    # Read-only metadata
    commentCount:  Optional[int]       = None
    createdTime:   Optional[str]       = None
    modifiedTime:  Optional[str]       = None
    etag:          Optional[str]       = None
    creator:       Optional[int]       = None

    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    def is_abandoned(self) -> bool:
        return self.status == TaskStatus.ABANDONED

    def priority_label(self) -> str:
        return Priority.label(self.priority)

    def checklist_progress(self) -> Optional[str]:
        if not self.items:
            return None
        done = sum(1 for i in self.items if i.is_completed())
        return f"{done}/{len(self.items)}"

    def effective_repeat(self) -> Optional[str]:
        return self.repeatFlag or self.repeat

    def effective_all_day(self) -> Optional[bool]:
        if self.isAllDay is not None:
            return self.isAllDay
        return self.allDay


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id:             str
    name:           str
    color:          Optional[str]   = None
    closed:         Optional[bool]  = False
    groupId:        Optional[str]   = None
    viewMode:       Optional[str]   = None
    kind:           Optional[str]   = "TASK"
    permission:     Optional[str]   = None
    sortOrder:      Optional[int]   = None
    sortType:       Optional[str]   = None
    isOwner:        Optional[bool]  = None
    inAll:          Optional[bool]  = None
    muted:          Optional[bool]  = None
    userCount:      Optional[int]   = None
    teamId:         Optional[str]   = None
    transferred:    Optional[str]   = None
    modifiedTime:   Optional[str]   = None
    etag:           Optional[str]   = None


class Column(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id:        Optional[str] = None
    projectId: Optional[str] = None
    name:      Optional[str] = None
    sortOrder: Optional[int] = None


class ProjectGroup(BaseModel):
    """Project folder/group (V2 only)."""
    model_config = ConfigDict(extra="ignore")

    id:        Optional[str]  = None
    name:      Optional[str]  = None
    listType:  Optional[str]  = None
    sortOrder: Optional[int]  = None
    showAll:   Optional[bool] = None
    sortType:  Optional[str]  = None
    etag:      Optional[str]  = None
    deleted:   Optional[int]  = None
    userId:    Optional[int]  = None
    teamId:    Optional[str]  = None


class ProjectData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project: Optional[Project]  = None
    tasks:   list[Task]         = Field(default_factory=list)
    columns: list[Column]       = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
#  Tags (V2 only)
# ═══════════════════════════════════════════════════════════════════════════════

class Tag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name:      str
    label:     Optional[str] = None
    color:     Optional[str] = None
    parent:    Optional[str] = None
    sortOrder: Optional[int] = None
    sortType:  Optional[str] = None
    etag:      Optional[str] = None
    rawName:   Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Habits (V2 only)
# ═══════════════════════════════════════════════════════════════════════════════

class Habit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id:              Optional[str]   = None
    name:            str             = ""
    status:          int             = HabitStatus.ACTIVE
    type:            Optional[str]   = HabitType.BOOLEAN
    goal:            Optional[float] = None
    step:            Optional[float] = None
    unit:            Optional[str]   = None
    iconRes:         Optional[str]   = None
    color:           Optional[str]   = None
    totalCheckIns:   Optional[int]   = None
    currentStreak:   Optional[int]   = None
    maxStreak:       Optional[int]   = None
    repeatRule:      Optional[str]   = None
    reminders:       Optional[list[str]] = Field(default_factory=list)
    encouragement:   Optional[str]   = None
    targetDays:      Optional[int]   = None
    sectionId:       Optional[str]   = None
    sortOrder:       Optional[int]   = None
    createdTime:     Optional[str]   = None
    modifiedTime:    Optional[str]   = None
    etag:            Optional[str]   = None
    startDate:       Optional[str]   = None
    completedCycles: Optional[int]   = None
    archivedTime:    Optional[str]   = None

    def is_archived(self) -> bool:
        return self.status == HabitStatus.ARCHIVED


class HabitSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id:        Optional[str] = None
    name:      Optional[str] = None
    sortOrder: Optional[int] = None


class HabitCheckin(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id:           Optional[str]   = None
    habitId:      Optional[str]   = None
    checkinStamp: Optional[int]   = None
    checkinTime:  Optional[str]   = None
    opTime:       Optional[str]   = None
    value:        Optional[float] = None
    goal:         Optional[float] = None
    status:       Optional[int]   = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Focus / Pomodoro (V2 only)
# ═══════════════════════════════════════════════════════════════════════════════

class FocusRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date:     Optional[str] = None
    duration: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  User & Statistics (V2 only)
# ═══════════════════════════════════════════════════════════════════════════════

class UserStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    userId:       Optional[int]  = None
    username:     Optional[str]  = None
    inboxId:      Optional[str]  = None
    pro:          Optional[bool] = None
    proStartDate: Optional[str]  = None
    proEndDate:   Optional[str]  = None
    teamUser:     Optional[bool] = None
    activeTeamUser: Optional[bool] = None
    freeTrial:    Optional[bool] = None
    needSubscribe: Optional[bool] = None


class ProductivityStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score:              Optional[int] = None
    level:              Optional[int] = None
    completedToday:     Optional[int] = None
    completedYesterday: Optional[int] = None
    completedThisWeek:  Optional[int] = None
    completedThisMonth: Optional[int] = None
    currentStreak:      Optional[int] = None
    maxStreak:          Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Sync Response (V2)
# ═══════════════════════════════════════════════════════════════════════════════

class SyncTaskBean(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update: list[Task] = Field(default_factory=list)


class SyncResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    inboxId:          Optional[str]            = None
    projectProfiles:  list[Project]            = Field(default_factory=list)
    projectGroups:    Optional[list[ProjectGroup]] = Field(default_factory=list)
    syncTaskBean:     Optional[SyncTaskBean]   = None
    tags:             list[Tag]                = Field(default_factory=list)
    checkPoint:       Optional[int]            = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Batch Payloads
# ═══════════════════════════════════════════════════════════════════════════════

class BatchDeleteItem(BaseModel):
    taskId:    str
    projectId: str


class BatchTaskPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[BatchDeleteItem] = Field(default_factory=list)
    addAttachments:    list[dict] = Field(default_factory=list)
    updateAttachments: list[dict] = Field(default_factory=list)
    deleteAttachments: list[dict] = Field(default_factory=list)


class BatchProjectPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[str]  = Field(default_factory=list)


class BatchGroupPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[str]  = Field(default_factory=list)


class BatchColumnPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[dict] = Field(default_factory=list)


class BatchTagPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)


class BatchHabitPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[str]  = Field(default_factory=list)


class BatchCheckinPayload(BaseModel):
    add:    list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    delete: list[str]  = Field(default_factory=list)


class BatchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id2etag:  dict[str, str] = Field(default_factory=dict)
    id2error: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
#  API Error
# ═══════════════════════════════════════════════════════════════════════════════

class TickTickAPIError(Exception):
    """Raised when the TickTick API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")

    def to_dict(self) -> dict[str, Any]:
        return {"error": True, "status_code": self.status_code, "message": self.message}