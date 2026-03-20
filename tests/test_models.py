"""
Unit tests for tick_mcp.models — Pydantic models, enums, helpers.

These are pure logic tests: no I/O, no network, no secrets.
They validate model construction, serialization, and helper functions.
"""
from __future__ import annotations

import pytest

from tick_mcp.models import (
    # Enums
    Priority, TaskStatus, ChecklistStatus, TaskKind, ProjectKind,
    HabitType, HabitStatus,
    # Models
    Task, Project, Column, Tag, Habit, HabitSection, HabitCheckin,
    ChecklistItem, ProjectGroup, ProjectData,
    SyncResponse, SyncTaskBean, BatchResponse,
    UserStatus, ProductivityStats,
    # Helpers
    build_reminder_trigger, build_rrule,
    # Error
    TickTickAPIError,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriority:
    def test_values(self):
        assert Priority.NONE == 0
        assert Priority.LOW == 1
        assert Priority.MEDIUM == 3
        assert Priority.HIGH == 5

    def test_label(self):
        assert Priority.label(0) == "none"
        assert Priority.label(1) == "low"
        assert Priority.label(3) == "medium"
        assert Priority.label(5) == "high"
        assert Priority.label(99) == "99"  # unknown → str fallback


class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.NORMAL == 0
        assert TaskStatus.COMPLETED == 2
        assert TaskStatus.ABANDONED == -1


class TestChecklistStatus:
    def test_values(self):
        assert ChecklistStatus.NORMAL == 0
        assert ChecklistStatus.COMPLETED == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  iCalendar Helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildReminderTrigger:
    def test_at_due_time(self):
        assert build_reminder_trigger(0) == "TRIGGER:PT0S"

    def test_30_minutes_before(self):
        assert build_reminder_trigger(30) == "TRIGGER:-PT30M"

    def test_1_hour_before(self):
        assert build_reminder_trigger(60) == "TRIGGER:-PT1H"

    def test_90_minutes_before(self):
        # 1h30m
        assert build_reminder_trigger(90) == "TRIGGER:-PT1H30M"

    def test_1_day_before(self):
        assert build_reminder_trigger(1440) == "TRIGGER:-P1D"

    def test_2_days_before(self):
        assert build_reminder_trigger(2880) == "TRIGGER:-P2D"

    def test_1_day_2_hours(self):
        # 1440 + 120 = 1560 min
        assert build_reminder_trigger(1560) == "TRIGGER:-P1DT2H"


class TestBuildRrule:
    def test_daily(self):
        assert build_rrule("DAILY") == "RRULE:FREQ=DAILY"

    def test_weekly_with_days(self):
        r = build_rrule("WEEKLY", by_day=["MO", "WE", "FR"])
        assert r == "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"

    def test_monthly_by_day(self):
        r = build_rrule("MONTHLY", by_month_day=15)
        assert r == "RRULE:FREQ=MONTHLY;BYMONTHDAY=15"

    def test_interval(self):
        r = build_rrule("DAILY", interval=3)
        assert "INTERVAL=3" in r

    def test_count(self):
        r = build_rrule("DAILY", count=10)
        assert "COUNT=10" in r

    def test_until(self):
        r = build_rrule("DAILY", until="20261231T000000Z")
        assert "UNTIL=20261231T000000Z" in r

    def test_tt_times(self):
        r = build_rrule("WEEKLY", tt_times=5)
        assert "TT_TIMES=5" in r

    def test_case_insensitive(self):
        r = build_rrule("weekly")
        assert "FREQ=WEEKLY" in r


# ═══════════════════════════════════════════════════════════════════════════════
#  Task Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaskModel:
    def test_minimal_construction(self):
        t = Task(title="Buy milk")
        assert t.title == "Buy milk"
        assert t.status == TaskStatus.NORMAL
        assert t.priority == Priority.NONE
        assert t.is_completed() is False

    def test_completed_task(self):
        t = Task(title="Done", status=2)
        assert t.is_completed() is True
        assert t.is_abandoned() is False

    def test_abandoned_task(self):
        t = Task(title="Nope", status=-1)
        assert t.is_abandoned() is True
        assert t.is_completed() is False

    def test_priority_label(self):
        t = Task(title="Urgent", priority=5)
        assert t.priority_label() == "high"

    def test_checklist_progress(self):
        t = Task(
            title="Shopping",
            items=[
                ChecklistItem(title="Eggs", status=1),
                ChecklistItem(title="Milk", status=0),
                ChecklistItem(title="Bread", status=1),
            ],
        )
        assert t.checklist_progress() == "2/3"

    def test_checklist_progress_empty(self):
        t = Task(title="Empty")
        assert t.checklist_progress() is None

    def test_effective_repeat(self):
        t1 = Task(title="R1", repeatFlag="RRULE:FREQ=DAILY")
        assert t1.effective_repeat() == "RRULE:FREQ=DAILY"
        t2 = Task(title="R2", repeat="RRULE:FREQ=WEEKLY")
        assert t2.effective_repeat() == "RRULE:FREQ=WEEKLY"

    def test_effective_all_day(self):
        t1 = Task(title="A", isAllDay=True)
        assert t1.effective_all_day() is True
        t2 = Task(title="B", allDay=False)
        assert t2.effective_all_day() is False
        t3 = Task(title="C")
        assert t3.effective_all_day() is None

    def test_extra_fields_ignored(self):
        """API may return unknown fields — they must not break parsing."""
        t = Task.model_validate({"title": "X", "unknownField": 42, "newApiField": "test"})
        assert t.title == "X"

    def test_full_api_payload(self):
        """Simulate a realistic V2 API response."""
        payload = {
            "id": "abc123",
            "projectId": "proj456",
            "title": "Review PR",
            "content": "Check the diff",
            "priority": 3,
            "status": 0,
            "dueDate": "2026-03-10T09:00:00+0000",
            "tags": ["work", "code-review"],
            "items": [
                {"id": "sub1", "title": "Read changes", "status": 1},
                {"id": "sub2", "title": "Leave comment", "status": 0},
            ],
            "modifiedTime": "2026-03-06T12:00:00+0000",
            "etag": "abc",
        }
        t = Task.model_validate(payload)
        assert t.id == "abc123"
        assert t.projectId == "proj456"
        assert t.priority_label() == "medium"
        assert len(t.tags) == 2
        assert t.checklist_progress() == "1/2"
        assert t.items[0].is_completed() is True


# ═══════════════════════════════════════════════════════════════════════════════
#  Project Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectModel:
    def test_minimal(self):
        p = Project(id="p1", name="Work")
        assert p.id == "p1"
        assert p.name == "Work"
        assert p.closed is False

    def test_extra_fields_ignored(self):
        p = Project.model_validate({"id": "p1", "name": "X", "futureField": True})
        assert p.name == "X"


# ═══════════════════════════════════════════════════════════════════════════════
#  Tag Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestTagModel:
    def test_minimal(self):
        t = Tag(name="urgent")
        assert t.name == "urgent"
        assert t.color is None

    def test_full(self):
        t = Tag.model_validate({"name": "work", "label": "Work", "color": "#ff0000"})
        assert t.color == "#ff0000"


# ═══════════════════════════════════════════════════════════════════════════════
#  Habit Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestHabitModel:
    def test_minimal(self):
        h = Habit(name="Meditate")
        assert h.name == "Meditate"
        assert h.is_archived() is False

    def test_archived(self):
        h = Habit(name="Old", status=2)
        assert h.is_archived() is True


# ═══════════════════════════════════════════════════════════════════════════════
#  Sync Response
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyncResponse:
    def test_empty_sync(self):
        s = SyncResponse.model_validate({})
        assert s.projectProfiles == []
        assert s.tags == []
        assert s.syncTaskBean is None

    def test_with_tasks(self):
        s = SyncResponse.model_validate({
            "syncTaskBean": {
                "update": [
                    {"title": "Task 1", "id": "t1", "projectId": "p1"},
                    {"title": "Task 2", "id": "t2", "projectId": "p1"},
                ]
            },
            "tags": [{"name": "work"}],
            "projectProfiles": [{"id": "p1", "name": "Inbox"}],
        })
        assert len(s.syncTaskBean.update) == 2
        assert len(s.tags) == 1
        assert s.projectProfiles[0].name == "Inbox"


# ═══════════════════════════════════════════════════════════════════════════════
#  Batch Response
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchResponse:
    def test_empty(self):
        b = BatchResponse.model_validate({})
        assert b.id2etag == {}
        assert b.id2error == {}

    def test_with_data(self):
        b = BatchResponse.model_validate({
            "id2etag": {"t1": "etag1", "t2": "etag2"},
            "id2error": {},
        })
        assert len(b.id2etag) == 2


# ═══════════════════════════════════════════════════════════════════════════════
#  TickTickAPIError
# ═══════════════════════════════════════════════════════════════════════════════

class TestTickTickAPIError:
    def test_construction(self):
        e = TickTickAPIError(401, "Unauthorized")
        assert e.status_code == 401
        assert e.message == "Unauthorized"
        assert "[401]" in str(e)

    def test_to_dict(self):
        e = TickTickAPIError(404, "Not found")
        d = e.to_dict()
        assert d["error"] is True
        assert d["status_code"] == 404
        assert d["message"] == "Not found"

    def test_is_exception(self):
        with pytest.raises(TickTickAPIError):
            raise TickTickAPIError(500, "Server error")


# ═══════════════════════════════════════════════════════════════════════════════
#  UserStatus
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserStatus:
    def test_minimal(self):
        u = UserStatus.model_validate({})
        assert u.userId is None
        assert u.pro is None

    def test_full(self):
        u = UserStatus.model_validate({
            "userId": 12345,
            "username": "kpihx",
            "inboxId": "inbox123",
            "pro": True,
        })
        assert u.userId == 12345
        assert u.pro is True
