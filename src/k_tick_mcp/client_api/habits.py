"""
Habit operations.
"""
from __future__ import annotations

from ..models import Habit, HabitSection
from .transport import _v2_get, _v2_post, _v2_delete

def get_habits() -> list[Habit]:
    """GET /habits — list all habits."""
    data = _v2_get("/habits")
    if isinstance(data, list):
        return [Habit.model_validate(h) for h in data]
    return []


def get_habit_sections() -> list[HabitSection]:
    """GET /habitSections — list habit sections (morning/afternoon/night)."""
    data = _v2_get("/habitSections")
    if isinstance(data, list):
        return [HabitSection.model_validate(s) for s in data]
    return []


def batch_habits(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[str] | None = None,
) -> dict | list:
    """POST /habits/batch — create, update, delete habits."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/habits/batch", payload)


def query_habit_checkins(habit_ids: list[str], after_stamp: int = 0) -> dict:
    """POST /habitCheckins/query — get check-in records for habits.

    Args:
        habit_ids: List of habit IDs to query.
        after_stamp: YYYYMMDD integer. 0 = all history.

    Returns dict: {"checkins": {"habitId": [HabitCheckin, ...]}}
    """
    payload = {"habitIds": habit_ids, "afterStamp": after_stamp}
    data = _v2_post("/habitCheckins/query", payload)
    return data if isinstance(data, dict) else {}


def batch_habit_checkins(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[str] | None = None,
) -> dict | list:
    """POST /habitCheckins/batch — create, update, delete check-ins."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/habitCheckins/batch", payload)


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Focus / Pomodoro
# ═══════════════════════════════════════════════════════════════════════════════


def get_habits_raw() -> list[dict]:
    """Return the raw V2 habit payload list without pydantic normalization."""
    data = _v2_get('/habits')
    return data if isinstance(data, list) else []

__all__ = [
    'get_habits', 'get_habits_raw', 'get_habit_sections', 'batch_habits',
    'query_habit_checkins', 'batch_habit_checkins',
]
