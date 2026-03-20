"""Habit MCP tools."""
from __future__ import annotations

from typing import Any, Optional

from .core import (
    mcp,
    TOOL_CATALOG,
    COMMON_WORKFLOWS,
    _err,
    _task_dict,
    _model_list,
    client,
    TickTickAPIError,
    Priority,
    has_v2_auth,
    ENV_SESSION_TOKEN,
    SESSION_COOKIE_NAME,
    build_reminder_trigger,
    build_rrule,
)

@mcp.tool()
def list_habits() -> list[dict]:
    """
    List all habits with stats (streaks, total check-ins, etc.).

    [Category: Habits]  [Auth: V2]
    [Related: create_habit, update_habit, habit_checkin, get_habit_records, list_habit_sections]

    Returns: id, name, status, type (Boolean/Real), goal, step, unit, color,
             totalCheckIns, currentStreak, maxStreak, repeatRule, sectionId, etc.
    """
    try:
        return _model_list(client.get_habits())
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def list_habit_sections() -> list[dict]:
    """
    List habit sections (e.g., Morning, Afternoon, Evening).

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, create_habit]

    Use section IDs in create_habit/update_habit to organize habits by time of day.
    """
    try:
        return _model_list(client.get_habit_sections())
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def create_habit(
    name: str,
    habit_type: str = "Boolean",
    goal: Optional[float] = None,
    step: Optional[float] = None,
    unit: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    section_id: Optional[str] = None,
    repeat_rule: Optional[str] = None,
    reminders: Optional[list[str]] = None,
    encouragement: Optional[str] = None,
    target_days: Optional[int] = None,
    start_date: Optional[str] = None,
) -> dict:
    """
    Create a new habit.

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, update_habit, habit_checkin, build_recurrence_rule]
    [Workflow: create_habit → habit_checkin daily → get_habit_records to review]

    Args:
        name: Habit name (required).
        habit_type: "Boolean" (done/not done) or "Real" (measurable, needs goal).
        goal: Target value for Real habits (e.g., 2.0 for "2L water").
        step: Increment step for Real (e.g., 0.25 for quarter-liter).
        unit: Measurement unit for Real (e.g., "L", "pages", "min").
        color: Hex color, e.g. "#4DB6AC".
        icon: Icon resource name.
        section_id: Section ID (from list_habit_sections) for time-of-day grouping.
        repeat_rule: RRULE string (use build_recurrence_rule). Default = daily.
        reminders: Time strings, e.g. ["08:00", "20:00"].
        encouragement: Message shown on completion.
        target_days: Target days for the habit goal cycle.
        start_date: "yyyy-MM-dd".

    Examples:
        Boolean: create_habit(name="Meditate", color="#7E57C2")
        Real:    create_habit(name="Read", habit_type="Real", goal=30, step=5, unit="pages")
    """
    try:
        habit: dict = {"name": name, "type": habit_type, "status": 0}
        if goal is not None:        habit["goal"] = goal
        if step is not None:        habit["step"] = step
        if unit:                    habit["unit"] = unit
        if color:                   habit["color"] = color
        if icon:                    habit["iconRes"] = icon
        if section_id:              habit["sectionId"] = section_id
        if repeat_rule:             habit["repeatRule"] = repeat_rule
        if reminders:               habit["reminders"] = reminders
        if encouragement:           habit["encouragement"] = encouragement
        if target_days is not None: habit["targetDays"] = target_days
        if start_date:              habit["startDate"] = start_date
        result = client.batch_habits(add=[habit])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def update_habit(
    habit_id: str,
    name: Optional[str] = None,
    goal: Optional[float] = None,
    step: Optional[float] = None,
    unit: Optional[str] = None,
    color: Optional[str] = None,
    status: Optional[int] = None,
    section_id: Optional[str] = None,
    repeat_rule: Optional[str] = None,
    reminders: Optional[list[str]] = None,
    encouragement: Optional[str] = None,
    target_days: Optional[int] = None,
) -> dict:
    """
    Update an existing habit. Only provided fields are changed
    (read-modify-write under the hood — safe for partial updates).

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, create_habit, delete_habit]

    Args:
        habit_id: The habit ID to update.
        name: New name.
        goal: New target value (Real habits).
        step: New increment step.
        unit: New measurement unit.
        color: New hex color.
        status: 0=active, 2=archived.
        section_id: Move to a different section.
        repeat_rule: New RRULE (use build_recurrence_rule).
        reminders: New reminder times list, e.g. ["08:00", "20:00"].
                   Pass [] to clear all reminders.
        encouragement: New completion message.
        target_days: New target days.

    ⚠️  CRITICAL — V2 /habits/batch is a FULL REPLACEMENT, not a PATCH:
        Sending only {"id": ..., "reminders": [...]} will wipe name, color,
        status and every other field to null/default. This tool prevents that
        by fetching the current habit state first, then merging your changes
        before sending the complete object. Never call client.batch_habits
        with a partial habit dict directly.

    Common uses:
        Archive:        update_habit(habit_id="...", status=2)
        Rename:         update_habit(habit_id="...", name="New Name")
        Add reminders:  update_habit(habit_id="...", reminders=["08:00", "20:00"])
        Clear reminders: update_habit(habit_id="...", reminders=[])
    """
    try:
        # Read current state — V2 /habits/batch replaces the entire object,
        # so we must fetch first to avoid wiping all unprovided fields.
        all_habits: list = client._v2_get("/habits")
        current = next((h for h in all_habits if h.get("id") == habit_id), None)
        if current is None:
            return {"error": True, "status_code": 404, "message": f"Habit {habit_id} not found."}

        # Start from existing state, then apply caller overrides.
        habit: dict = {k: v for k, v in current.items()}
        habit["id"] = habit_id
        if name is not None:           habit["name"] = name
        if goal is not None:           habit["goal"] = goal
        if step is not None:           habit["step"] = step
        if unit is not None:           habit["unit"] = unit
        if color is not None:          habit["color"] = color
        if status is not None:         habit["status"] = status
        if section_id is not None:     habit["sectionId"] = section_id
        if repeat_rule is not None:    habit["repeatRule"] = repeat_rule
        if reminders is not None:      habit["reminders"] = reminders
        if encouragement is not None:  habit["encouragement"] = encouragement
        if target_days is not None:    habit["targetDays"] = target_days
        result = client.batch_habits(update=[habit])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def delete_habit(habit_id: str) -> dict:
    """
    Delete a habit permanently.

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, update_habit]

    Args:
        habit_id: The habit ID to delete.
    """
    try:
        result = client.batch_habits(delete=[habit_id])
        return result if isinstance(result, dict) else {"success": True, "deleted_habit_id": habit_id}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def habit_checkin(
    habit_id: str,
    checkin_stamp: int,
    value: Optional[float] = None,
    status: int = 2,
    checkin_time: Optional[str] = None,
) -> dict:
    """
    Record a habit check-in (mark as done for a specific day).

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, get_habit_records, create_habit]

    Args:
        habit_id: The habit ID.
        checkin_stamp: Date as YYYYMMDD integer, e.g. 20260306 for today.
        value: Value for Real habits (e.g., 1.5 for "1.5 liters"). Omit for Boolean.
        status: 0=unchecked, 2=completed (default: 2).
        checkin_time: ISO datetime for exact time (optional).
    """
    try:
        checkin: dict = {"habitId": habit_id, "checkinStamp": checkin_stamp, "status": status}
        if value is not None:  checkin["value"] = value
        if checkin_time:       checkin["checkinTime"] = checkin_time
        result = client.batch_habit_checkins(add=[checkin])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def get_habit_records(
    habit_ids: list[str],
    after_stamp: int = 0,
) -> dict:
    """
    Get check-in records for one or more habits.

    [Category: Habits]  [Auth: V2]
    [Related: list_habits, habit_checkin]

    Args:
        habit_ids: List of habit IDs to query.
        after_stamp: Only return check-ins after this date (YYYYMMDD, e.g. 20260101).
            Use 0 for all history.

    Returns: {"checkins": {"habitId": [record, ...]}}
    """
    try:
        return client.query_habit_checkins(habit_ids, after_stamp)
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  🍅 FOCUS / POMODORO (V2)
# ═══════════════════════════════════════════════════════════════════════════════
