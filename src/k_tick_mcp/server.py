"""
TickTick MCP Server v0.2 — comprehensive tool definitions.

Every tool docstring follows a structured format to help the LLM:
  - First line: short action summary
  - [Category: ...] — grouping for navigation
  - [Auth: V1] or [Auth: V2] — which token is needed
  - [Related: ...] — cross-references to related tools
  - [Workflow: ...] — common multi-step patterns (optional)

All tools return plain dicts/lists (JSON-serializable).
Errors never raise — they return {"error": True, "status_code": N, "message": "..."}.
"""
from __future__ import annotations

from typing import Optional, Any

from mcp.server.fastmcp import FastMCP

from .config import SERVER_NAME, has_v2_auth, ENV_SESSION_TOKEN, SESSION_COOKIE_NAME
from . import client
from .models import (
    TickTickAPIError, TaskStatus, Priority,
    build_reminder_trigger, build_rrule,
)

mcp = FastMCP(SERVER_NAME)


# ═══════════════════════════════════════════════════════════════════════════════
#  Tool Catalog (used by ticktick_guide)
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_CATALOG = {
    "📋 Projects (V1)": {
        "tools": ["list_projects", "get_project_detail", "create_project", "update_project", "delete_project"],
        "desc": "CRUD operations on TickTick projects/lists.",
    },
    "✅ Tasks — Read (V1)": {
        "tools": ["get_inbox", "get_project_tasks", "get_task_detail"],
        "desc": "Fetch tasks from inbox or specific projects.",
    },
    "✏️ Tasks — Write (V1)": {
        "tools": ["create_task", "update_task", "complete_task", "reopen_task", "delete_task"],
        "desc": "Create, modify, complete, reopen or delete tasks.",
    },
    "⚡ Tasks — Batch (V2)": {
        "tools": ["batch_create_tasks", "batch_update_tasks", "batch_delete_tasks", "move_tasks", "set_subtask_parent"],
        "desc": "Bulk task operations: create/update/delete many at once, move between projects, set parent-child.",
    },
    "🔄 Sync (V2)": {
        "tools": ["get_all_tasks", "full_sync"],
        "desc": "Full account sync — all tasks, projects, tags, folders in one call.",
    },
    "📦 Completed & Trash (V2)": {
        "tools": ["get_completed_tasks", "get_deleted_tasks"],
        "desc": "Access completed/abandoned tasks and trash.",
    },
    "📁 Folders (V2)": {
        "tools": ["list_project_folders", "manage_project_folders"],
        "desc": "Organize projects into folders/groups.",
    },
    "📊 Kanban Columns (V2)": {
        "tools": ["list_columns", "manage_columns"],
        "desc": "Manage kanban board columns within a project.",
    },
    "🏷️ Tags (V2)": {
        "tools": ["list_tags", "create_tag", "update_tag", "rename_tag", "merge_tags", "delete_tag"],
        "desc": "Full tag management: create, update, rename, merge, delete.",
    },
    "🔁 Habits (V2)": {
        "tools": ["list_habits", "list_habit_sections", "create_habit", "update_habit", "delete_habit", "habit_checkin", "get_habit_records"],
        "desc": "Habit tracking: create habits, check in, view streaks & records.",
    },
    "🍅 Focus / Pomodoro (V2)": {
        "tools": ["get_focus_stats"],
        "desc": "Focus session statistics: heatmap and per-tag distribution.",
    },
    "👤 User & Stats (V2)": {
        "tools": ["get_user_status", "get_productivity_stats"],
        "desc": "Account info, subscription status, productivity scores & streaks.",
    },
    "🛠️ Utilities": {
        "tools": ["ticktick_guide", "check_v2_availability", "build_recurrence_rule", "build_reminder"],
        "desc": "Helpers: tool catalog, V2 check, RRULE builder, reminder builder.",
    },
}

COMMON_WORKFLOWS = [
    {
        "name": "Create task with subtasks",
        "steps": [
            "1. create_task(title='Parent task', project_id='...')",
            "2. create_task(title='Subtask 1', project_id='...')",
            "3. set_subtask_parent(task_id=<subtask_id>, project_id='...', parent_id=<parent_id>)",
        ],
    },
    {
        "name": "Create recurring task with reminder",
        "steps": [
            "1. build_recurrence_rule(frequency='WEEKLY', by_day=['MO','WE','FR']) → get rrule",
            "2. create_task(title='...', recurrence=<rrule>, reminder_minutes=[30], due_date='...', time_zone='Europe/Paris')",
        ],
    },
    {
        "name": "Move tasks to a new project",
        "steps": [
            "1. create_project(name='New Project') → get project id",
            "2. move_tasks([{'taskId': '...', 'fromProjectId': '...', 'toProjectId': '<new_id>'}])",
        ],
    },
    {
        "name": "Organize with Eisenhower matrix",
        "steps": [
            "1. create_project(name='Eisenhower', view_mode='kanban')",
            "2. manage_columns(project_id='...', add=[{'name':'Urgent+Important'},{'name':'Important'},{'name':'Urgent'},{'name':'Neither'}])",
            "3. create_task(title='...', project_id='...', column_id='<column_id>', priority=5)",
        ],
    },
    {
        "name": "Track a measurable habit",
        "steps": [
            "1. create_habit(name='Drink water', habit_type='Real', goal=2.0, step=0.25, unit='L')",
            "2. habit_checkin(habit_id='...', checkin_stamp=20260306, value=0.5)",
            "3. get_habit_records(habit_ids=['...']) → view history",
        ],
    },
    {
        "name": "Full account overview",
        "steps": [
            "1. full_sync() → all projects, tasks, tags, folders in one call",
            "   OR list_projects() + get_all_tasks() for just projects & tasks",
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _err(e) -> dict:
    if isinstance(e, TickTickAPIError):
        return e.to_dict()
    return {"error": True, "message": str(e), "type": type(e).__name__}


def _task_dict(task) -> dict:
    """Serialize a Task model to a dict, adding human-readable labels."""
    d = task.model_dump(exclude_none=False)
    d["priority_label"] = task.priority_label()
    d["is_completed"] = task.is_completed()
    # Normalize allDay / isAllDay into a single reliable key
    d["allDay"] = task.effective_all_day()
    progress = task.checklist_progress()
    if progress:
        d["checklist_progress"] = progress
    return d


def _model_list(items) -> list[dict]:
    return [i.model_dump(exclude_none=False) for i in (items or [])]


# ═══════════════════════════════════════════════════════════════════════════════
#  🛠️ UTILITIES & DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def ticktick_guide(
    category: Optional[str] = None,
    show_workflows: bool = False,
) -> dict:
    """
    Interactive guide to all TickTick MCP tools — START HERE.

    [Category: Utilities]  [Auth: none]
    [Related: check_v2_availability]

    Call with no args to see all categories and tool names.
    Call with a category name to see tools in that category.
    Call with show_workflows=True to see common multi-step patterns.

    Args:
        category: Filter by category name (partial match, case-insensitive).
            Examples: "task", "tag", "habit", "project", "sync", "focus".
        show_workflows: If True, return common multi-step workflow recipes.

    Tip: Call check_v2_availability() to see which features need a session token.
    """
    if show_workflows:
        return {"workflows": COMMON_WORKFLOWS}

    if category:
        cat_lower = category.lower()
        filtered = {
            k: v for k, v in TOOL_CATALOG.items()
            if cat_lower in k.lower() or cat_lower in v["desc"].lower()
        }
        if not filtered:
            return {
                "error": False,
                "message": f"No category matching '{category}'. Available: {list(TOOL_CATALOG.keys())}",
            }
        return {"categories": filtered}

    # Full catalog — summary view
    summary = {}
    total = 0
    for cat, info in TOOL_CATALOG.items():
        summary[cat] = {"description": info["desc"], "tools": info["tools"], "count": len(info["tools"])}
        total += len(info["tools"])
    return {
        "total_tools": total,
        "categories": summary,
        "tip": "Call ticktick_guide(category='tasks') to drill into a category, or ticktick_guide(show_workflows=True) for step-by-step recipes.",
    }


@mcp.tool()
def check_v2_availability() -> dict:
    """
    Check whether V2 API features are available (session token configured).

    [Category: Utilities]  [Auth: none]
    [Related: ticktick_guide]

    Returns availability status and lists all V2-only feature categories.
    """
    available = has_v2_auth()
    v2_categories = [k for k in TOOL_CATALOG if "(V2)" in k]
    return {
        "v2_available": available,
        "message": "V2 features are enabled." if available else
                   f"V2 features unavailable. Set {ENV_SESSION_TOKEN} env var (extract '{SESSION_COOKIE_NAME}' cookie from TickTick web session).",
        "v2_categories": v2_categories,
    }


@mcp.tool()
def build_recurrence_rule(
    frequency: str,
    interval: int = 1,
    by_day: Optional[list[str]] = None,
    by_month_day: Optional[int] = None,
    by_month: Optional[int] = None,
    count: Optional[int] = None,
    until: Optional[str] = None,
) -> dict:
    """
    Build an iCalendar RRULE string for recurring tasks or habits.

    [Category: Utilities]  [Auth: none]
    [Related: create_task, update_task, create_habit]

    Args:
        frequency: "DAILY", "WEEKLY", "MONTHLY", or "YEARLY".
        interval: Repeat every N units (default 1).
        by_day: Weekday codes for WEEKLY, e.g. ["MO","WE","FR"].
        by_month_day: Day of month (1-31) for MONTHLY.
        by_month: Month number (1-12) for YEARLY.
        count: End after N occurrences.
        until: End date UTC: "20261231T000000Z".

    Examples:
        Every day          → frequency="DAILY"
        Mon/Wed/Fri        → frequency="WEEKLY", by_day=["MO","WE","FR"]
        15th of each month → frequency="MONTHLY", by_month_day=15
        Every 2 weeks      → frequency="WEEKLY", interval=2
        3 times then stop  → frequency="DAILY", count=3

    Returns {"rrule": "RRULE:FREQ=..."} — pass the rrule value as the
    'recurrence' parameter in create_task/update_task.
    """
    rule = build_rrule(
        frequency=frequency, interval=interval, by_day=by_day,
        by_month_day=by_month_day, by_month=by_month,
        count=count, until=until,
    )
    return {"rrule": rule}


@mcp.tool()
def build_reminder(minutes_before: int) -> dict:
    """
    Convert minutes into an iCalendar TRIGGER string for reminders.

    [Category: Utilities]  [Auth: none]
    [Related: create_task, update_task]

    Args:
        minutes_before: 0=at due time, 30=30min before, 60=1hr, 1440=1day, 2880=2days.

    Usually you don't need this — use the reminder_minutes parameter in create_task
    / update_task directly. This tool is for inspection or manual trigger building.
    """
    trigger = build_reminder_trigger(minutes_before)
    return {"trigger": trigger, "minutes_before": minutes_before}


# ═══════════════════════════════════════════════════════════════════════════════
#  📋 PROJECTS — V1
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_projects() -> list[dict]:
    """
    List all TickTick projects (lists).

    [Category: Projects]  [Auth: V1]
    [Related: get_project_detail, create_project, get_project_tasks, list_project_folders]

    Returns: id, name, kind (TASK/NOTE), closed, color, sortOrder, groupId.
    Use the returned 'id' as project_id in task tools.
    """
    try:
        return _model_list(client.get_projects())
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def get_project_detail(project_id: str) -> dict:
    """
    Get full details of a single project.

    [Category: Projects]  [Auth: V1]
    [Related: list_projects, get_project_tasks, update_project]

    Args:
        project_id: The project ID (from list_projects).
    """
    try:
        return client.get_project(project_id).model_dump(exclude_none=False)
    except TickTickAPIError as e:
        return _err(e)
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_project(
    name: str,
    color: Optional[str] = None,
    kind: str = "TASK",
    view_mode: Optional[str] = None,
    group_id: Optional[str] = None,
) -> dict:
    """
    Create a new TickTick project (list).

    [Category: Projects]  [Auth: V1]
    [Related: list_projects, update_project, delete_project, list_project_folders]
    [Workflow: Create project → manage_columns (for kanban) → create_task]

    Args:
        name: Project name (required).
        color: Hex color, e.g. "#F18181".
        kind: "TASK" (default) or "NOTE".
        view_mode: "list", "kanban", or "timeline".
        group_id: Folder ID to file project in (from list_project_folders).
    """
    try:
        payload: dict = {"name": name, "kind": kind}
        if color:
            payload["color"] = color
        if view_mode:
            payload["viewMode"] = view_mode
        if group_id:
            payload["groupId"] = group_id
        return client.create_project(payload).model_dump(exclude_none=False)
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def update_project(
    project_id: str,
    name: Optional[str] = None,
    color: Optional[str] = None,
    kind: Optional[str] = None,
    view_mode: Optional[str] = None,
    group_id: Optional[str] = None,
    closed: Optional[bool] = None,
) -> dict:
    """
    Update an existing project. Only provided fields are changed.

    [Category: Projects]  [Auth: V1]
    [Related: get_project_detail, create_project, delete_project]

    Args:
        project_id: The project to update.
        name: New name.
        color: Hex color.
        kind: "TASK" or "NOTE".
        view_mode: "list", "kanban", or "timeline".
        group_id: Move to a different folder.
        closed: True=archive, False=unarchive.
    """
    try:
        payload: dict = {}
        if name is not None:      payload["name"] = name
        if color is not None:     payload["color"] = color
        if kind is not None:      payload["kind"] = kind
        if view_mode is not None: payload["viewMode"] = view_mode
        if group_id is not None:  payload["groupId"] = group_id
        if closed is not None:    payload["closed"] = closed
        if not payload:
            return {"error": True, "status_code": 0, "message": "No fields provided."}
        return client.update_project(project_id, payload).model_dump(exclude_none=False)
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def delete_project(project_id: str) -> dict:
    """
    Permanently delete a project and ALL its tasks. ⚠️ IRREVERSIBLE.

    [Category: Projects]  [Auth: V1]
    [Related: list_projects, update_project]

    Args:
        project_id: The project to delete.
    """
    try:
        client.delete_project(project_id)
        return {"success": True, "deleted_project_id": project_id}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  ✅ TASKS — V1 Read
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_inbox(include_completed: bool = False) -> list[dict]:
    """
    Return tasks from the TickTick Inbox.

    [Category: Tasks — Read]  [Auth: V1]
    [Related: get_project_tasks, get_all_tasks, create_task]

    Args:
        include_completed: If True, include completed tasks (default: False).
    """
    try:
        data = client.get_inbox_data()
        tasks = data.tasks
        if not include_completed:
            tasks = [t for t in tasks if not t.is_completed()]
        return [_task_dict(t) for t in tasks]
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def get_project_tasks(project_id: str, include_completed: bool = False) -> list[dict]:
    """
    Return all tasks from a specific project, with kanban columns if available.

    [Category: Tasks — Read]  [Auth: V1]
    [Related: list_projects, get_task_detail, get_inbox, list_columns]

    Args:
        project_id: The project ID (use list_projects to find it).
        include_completed: If True, include completed tasks (default: False).
    """
    try:
        data = client.get_project_data(project_id)
        tasks = data.tasks
        if not include_completed:
            tasks = [t for t in tasks if not t.is_completed()]
        result: dict = {"tasks": [_task_dict(t) for t in tasks]}
        if data.columns:
            result["columns"] = _model_list(data.columns)
        return [result]
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def get_task_detail(project_id: str, task_id: str) -> dict:
    """
    Return full detail of a specific task: checklist, reminders, recurrence,
    tags, dates, subtask info, focus summaries, and all metadata.

    [Category: Tasks — Read]  [Auth: V1]
    [Related: get_project_tasks, update_task, complete_task]

    Args:
        project_id: The project containing the task.
        task_id: The task ID.
    """
    try:
        return _task_dict(client.get_task(project_id, task_id))
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  ✏️ TASKS — V1 Write
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_task(
    title: str,
    project_id: Optional[str] = None,
    content: Optional[str] = None,
    desc: Optional[str] = None,
    priority: int = Priority.NONE,
    due_date: Optional[str] = None,
    start_date: Optional[str] = None,
    time_zone: Optional[str] = None,
    tags: Optional[list[str]] = None,
    checklist_items: Optional[list[str]] = None,
    all_day: Optional[bool] = None,
    kind: Optional[str] = None,
    reminder_minutes: Optional[list[int]] = None,
    recurrence: Optional[str] = None,
    column_id: Optional[str] = None,
) -> dict:
    """
    Create a new TickTick task.

    [Category: Tasks — Write]  [Auth: V1]
    [Related: update_task, complete_task, set_subtask_parent, build_recurrence_rule]
    [Workflow: For subtasks → create_task then set_subtask_parent]

    Args:
        title: Task title (required).
        project_id: Target project ID. Omit → Inbox.
        content: Body / description (plain text or markdown).
        desc: Alt description field (used by some TickTick views).
        priority: 0=none, 1=low, 3=medium, 5=high (Eisenhower: 5=urgent+important).
        due_date: ISO 8601, e.g. "2026-03-10T09:00:00+0000".
        start_date: ISO 8601.
        time_zone: IANA timezone, e.g. "Europe/Paris". Recommended with dates.
        tags: Tag strings, e.g. ["work", "urgent"].
        checklist_items: Strings → each becomes a checklist item. Auto-sets kind=CHECKLIST.
        all_day: True for all-day (no specific time).
        kind: "TEXT", "NOTE", or "CHECKLIST". Auto-set if checklist_items given.
        reminder_minutes: Minutes before due to remind, e.g. [0, 30, 1440].
            0=at time, 30=30min before, 1440=1 day before.
        recurrence: RRULE string (use build_recurrence_rule to generate).
        column_id: Kanban column ID (for kanban-view projects).

    Returns the created task with its assigned id.
    """
    try:
        payload: dict = {"title": title, "priority": priority}
        if project_id:          payload["projectId"] = project_id
        if content:             payload["content"] = content
        if desc:                payload["desc"] = desc
        if due_date:            payload["dueDate"] = due_date
        if start_date:          payload["startDate"] = start_date
        if time_zone:           payload["timeZone"] = time_zone
        if tags:                payload["tags"] = tags
        if all_day is not None:
            payload["allDay"] = all_day
            payload["isAllDay"] = all_day
        if column_id:           payload["columnId"] = column_id
        if reminder_minutes:
            payload["reminders"] = [build_reminder_trigger(m) for m in reminder_minutes]
        if recurrence:
            payload["repeatFlag"] = recurrence
        if checklist_items:
            payload["items"] = [{"title": item, "status": TaskStatus.NORMAL} for item in checklist_items]
            payload["kind"] = "CHECKLIST"
        elif kind:
            payload["kind"] = kind

        return _task_dict(client.create_task(payload))
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def update_task(
    task_id: str,
    project_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    desc: Optional[str] = None,
    priority: Optional[int] = None,
    due_date: Optional[str] = None,
    start_date: Optional[str] = None,
    time_zone: Optional[str] = None,
    tags: Optional[list[str]] = None,
    status: Optional[int] = None,
    all_day: Optional[bool] = None,
    column_id: Optional[str] = None,
    reminder_minutes: Optional[list[int]] = None,
    recurrence: Optional[str] = None,
    progress: Optional[int] = None,
    sort_order: Optional[int] = None,
    kind: Optional[str] = None,
) -> dict:
    """
    Update any fields of an existing task. Only provided fields are changed
    (read-modify-write under the hood — safe for partial updates).

    [Category: Tasks — Write]  [Auth: V1]
    [Related: get_task_detail, create_task, complete_task, reopen_task]

    Args:
        task_id: The task to update.
        project_id: The project containing the task (required by API).
        title: New title.
        content: New body/description.
        desc: Alt description field.
        priority: 0=none, 1=low, 3=medium, 5=high.
        due_date: ISO 8601. Pass "" to clear.
        start_date: ISO 8601. Pass "" to clear.
        time_zone: IANA timezone.
        tags: Full replacement list. Pass [] to clear all tags.
        status: 0=active, 2=completed, -1=abandoned (V2).
        all_day: True/False.
        column_id: Move to a kanban column.
        reminder_minutes: List of minutes-before. Pass [] to clear reminders.
        recurrence: RRULE string (use build_recurrence_rule). Pass "" to clear.
        progress: 0-100 percentage (V2).
        sort_order: Custom sort order.
        kind: "TEXT", "NOTE", or "CHECKLIST".
    """
    try:
        fields: dict = {}
        _map = {
            "title": title, "content": content, "desc": desc,
            "priority": priority, "due_date": due_date, "start_date": start_date,
            "time_zone": time_zone, "tags": tags, "status": status,
            "allDay": all_day, "column_id": column_id, "progress": progress,
            "sort_order": sort_order, "kind": kind,
        }
        for k, v in _map.items():
            if v is not None:
                fields[k] = v
        # Keep allDay and isAllDay in sync
        if all_day is not None:
            fields["isAllDay"] = all_day
        if reminder_minutes is not None:
            fields["reminders"] = [build_reminder_trigger(m) for m in reminder_minutes]
        if recurrence is not None:
            fields["repeatFlag"] = recurrence
        if not fields:
            return {"error": True, "status_code": 0, "message": "No fields provided to update."}
        return _task_dict(client.update_task_fields(project_id, task_id, **fields))
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def complete_task(project_id: str, task_id: str) -> dict:
    """
    Mark a task as completed (status → 2). Uses V1 dedicated endpoint.

    [Category: Tasks — Write]  [Auth: V1]
    [Related: reopen_task, get_task_detail, get_completed_tasks]

    Args:
        project_id: The project containing the task.
        task_id: The task to complete.
    """
    try:
        return _task_dict(client.complete_task(project_id, task_id))
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def reopen_task(project_id: str, task_id: str) -> dict:
    """
    Reopen a completed task (status → 0).

    [Category: Tasks — Write]  [Auth: V1]
    [Related: complete_task, update_task]

    Args:
        project_id: The project containing the task.
        task_id: The task to reopen.
    """
    try:
        return _task_dict(client.reopen_task(project_id, task_id))
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def delete_task(project_id: str, task_id: str) -> dict:
    """
    Permanently delete a task. ⚠️ IRREVERSIBLE.

    [Category: Tasks — Write]  [Auth: V1]
    [Related: complete_task, get_deleted_tasks]

    Args:
        project_id: The project containing the task.
        task_id: The task to delete.
    """
    try:
        client.delete_task(project_id, task_id)
        return {"success": True, "deleted_task_id": task_id}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  🔄 SYNC (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_all_tasks() -> list[dict]:
    """
    Get ALL active tasks across all projects in one call via V2 sync.

    [Category: Sync]  [Auth: V2]
    [Related: full_sync, get_inbox, get_project_tasks]

    Much faster than iterating projects one by one. Returns a flat list.
    """
    try:
        return [_task_dict(t) for t in client.get_all_tasks()]
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def full_sync() -> dict:
    """
    Full V2 sync — all projects, tasks, tags, folders in ONE call.

    [Category: Sync]  [Auth: V2]
    [Related: get_all_tasks, list_projects, list_tags, list_project_folders]

    Returns: {inboxId, projects, tasks, tags, folders, task_count}.
    Best for getting a complete overview of the account.
    """
    try:
        sync = client.sync_all()
        result: dict[str, Any] = {"inboxId": sync.inboxId}
        result["projects"] = _model_list(sync.projectProfiles)
        result["folders"] = _model_list(sync.projectGroups)
        result["tags"] = _model_list(sync.tags)
        if sync.syncTaskBean:
            result["tasks"] = [_task_dict(t) for t in sync.syncTaskBean.update]
            result["task_count"] = len(sync.syncTaskBean.update)
        else:
            result["tasks"] = []
            result["task_count"] = 0
        return result
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  ⚡ BATCH TASK OPERATIONS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def batch_create_tasks(tasks: list[dict]) -> dict:
    """
    Create multiple tasks at once via V2 batch.

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: create_task, batch_update_tasks, batch_delete_tasks]

    Args:
        tasks: List of task dicts. Each needs at least {"title": "..."}.
            Optional: projectId, content, priority, dueDate, startDate,
            timeZone, tags, allDay, kind, items, columnId.

    Returns: {id2etag: {id: etag}, id2error: {id: error}} — check id2error for failures.
    """
    try:
        return client.batch_tasks(add=tasks).model_dump()
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def batch_update_tasks(tasks: list[dict]) -> dict:
    """
    Update multiple tasks at once via V2 batch.

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: update_task, batch_create_tasks, batch_delete_tasks]

    Args:
        tasks: List of task dicts. Each MUST include "id" and "projectId"
            plus fields to change. ⚠️ No read-modify-write — provide full field values.

    Returns: {id2etag, id2error}.
    """
    try:
        return client.batch_tasks(update=tasks).model_dump()
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def batch_delete_tasks(tasks: list[dict]) -> dict:
    """
    Delete multiple tasks at once via V2 batch.

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: delete_task, batch_create_tasks]

    Args:
        tasks: List of {"taskId": "...", "projectId": "..."}.
    """
    try:
        return client.batch_tasks(delete=tasks).model_dump()
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def move_tasks(moves: list[dict]) -> dict:
    """
    Move tasks between projects via V2 batch.

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: batch_update_tasks, list_projects]

    Args:
        moves: List of {"taskId": "...", "fromProjectId": "...", "toProjectId": "..."}.
    """
    try:
        result = client.move_tasks(moves)
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def set_subtask_parent(
    task_id: str,
    project_id: str,
    parent_id: Optional[str] = None,
    old_parent_id: Optional[str] = None,
) -> dict:
    """
    Set or unset a task's parent (subtask relationship).

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: create_task, get_task_detail]
    [Workflow: create_task → set_subtask_parent (TickTick ignores parentId on creation)]

    Args:
        task_id: The child task ID.
        project_id: The project both tasks belong to.
        parent_id: New parent task ID (to make subtask). Provide THIS to SET.
        old_parent_id: Previous parent ID (to remove). Provide THIS to UNSET.
            ⚠️ Provide EITHER parent_id OR old_parent_id, not both.
    """
    try:
        rel: dict = {"taskId": task_id, "projectId": project_id}
        if parent_id:
            rel["parentId"] = parent_id
        elif old_parent_id:
            rel["oldParentId"] = old_parent_id
        else:
            return {"error": True, "status_code": 0,
                    "message": "Provide either parent_id (to set) or old_parent_id (to unset)."}
        result = client.set_task_parent([rel])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  📦 COMPLETED & DELETED TASKS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_completed_tasks(
    from_date: str,
    to_date: str,
    status: str = "Completed",
    limit: int = 100,
) -> list[dict]:
    """
    Get completed or abandoned tasks within a date range.

    [Category: Completed & Trash]  [Auth: V2]
    [Related: complete_task, get_deleted_tasks, get_productivity_stats]

    Args:
        from_date: "yyyy-MM-dd HH:mm:ss", e.g. "2026-01-01 00:00:00".
        to_date: "yyyy-MM-dd HH:mm:ss", e.g. "2026-12-31 23:59:59".
        status: "Completed" or "Abandoned" (default: "Completed").
        limit: Max results (default 100).
    """
    try:
        return [_task_dict(t) for t in client.get_completed_tasks(from_date, to_date, status, limit)]
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def get_deleted_tasks(start: int = 0, limit: int = 50) -> list[dict]:
    """
    Get deleted tasks from the trash.

    [Category: Completed & Trash]  [Auth: V2]
    [Related: delete_task, get_completed_tasks]

    Args:
        start: Pagination offset (default 0).
        limit: Max results (default 50).
    """
    try:
        return [_task_dict(t) for t in client.get_deleted_tasks(start, limit)]
    except TickTickAPIError as e:
        return [_err(e)]


# ═══════════════════════════════════════════════════════════════════════════════
#  📁 PROJECT FOLDERS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_project_folders() -> list[dict]:
    """
    List all project folders (groups).

    [Category: Folders]  [Auth: V2]
    [Related: manage_project_folders, create_project, list_projects]

    Returns: id, name, sortOrder. Use folder IDs as group_id in create/update_project.
    """
    try:
        return _model_list(client.get_project_groups())
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def manage_project_folders(
    add: Optional[list[dict]] = None,
    update: Optional[list[dict]] = None,
    delete: Optional[list[str]] = None,
) -> dict:
    """
    Create, update, or delete project folders in batch.

    [Category: Folders]  [Auth: V2]
    [Related: list_project_folders, create_project]

    Args:
        add: New folders: [{"name": "Work"}, {"name": "Personal"}].
        update: Updates: [{"id": "...", "name": "New Name"}].
        delete: Folder IDs to delete: ["id1", "id2"].
    """
    try:
        result = client.batch_project_groups(add=add, update=update, delete=delete)
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  📊 KANBAN COLUMNS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_columns(project_id: str) -> list[dict]:
    """
    List kanban columns for a project.

    [Category: Kanban Columns]  [Auth: V2]
    [Related: manage_columns, get_project_tasks, create_task]

    Args:
        project_id: The project with kanban view mode.
    """
    try:
        return _model_list(client.get_columns(project_id))
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def manage_columns(
    project_id: str,
    add: Optional[list[dict]] = None,
    update: Optional[list[dict]] = None,
    delete: Optional[list[str]] = None,
) -> dict:
    """
    Create, update, or delete kanban columns in batch.

    [Category: Kanban Columns]  [Auth: V2]
    [Related: list_columns, create_task, update_task]
    [Workflow: Create kanban project → manage_columns → create_task with column_id]

    Args:
        project_id: The project these columns belong to.
        add: New columns: [{"name": "To Do", "sortOrder": 0}, {"name": "In Progress", "sortOrder": 1}].
            projectId is auto-filled.
        update: Column updates: [{"id": "...", "name": "New Name"}].
        delete: Column IDs to delete.
    """
    try:
        add_list = add or []
        for col in add_list:
            col.setdefault("projectId", project_id)
        delete_list = [{"id": cid, "projectId": project_id} for cid in (delete or [])]
        result = client.batch_columns(add=add_list, update=update, delete=delete_list)
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  🏷️ TAGS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_tags() -> list[dict]:
    """
    List all tags.

    [Category: Tags]  [Auth: V2]
    [Related: create_tag, update_tag, rename_tag, merge_tags, delete_tag]

    Returns: name (internal key, lowercase), label (display), color, parent, sortOrder.
    Use tag names in create_task/update_task tags parameter.
    """
    try:
        return _model_list(client.get_tags())
    except TickTickAPIError as e:
        return [_err(e)]


@mcp.tool()
def create_tag(
    name: str,
    color: Optional[str] = None,
    parent: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> dict:
    """
    Create a new tag.

    [Category: Tags]  [Auth: V2]
    [Related: list_tags, update_tag, rename_tag, delete_tag]

    Args:
        name: Tag name/label.
        color: Hex color, e.g. "#FF6B6B".
        parent: Parent tag name (for nested/hierarchical tags).
        sort_type: "project", "dueDate", "title", or "priority".
    """
    try:
        tag: dict = {"name": name, "label": name}
        if color:     tag["color"] = color
        if parent:    tag["parent"] = parent
        if sort_type: tag["sortType"] = sort_type
        result = client.batch_tags(add=[tag])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def update_tag(
    name: str,
    color: Optional[str] = None,
    parent: Optional[str] = None,
    sort_type: Optional[str] = None,
    sort_order: Optional[int] = None,
) -> dict:
    """
    Update an existing tag's properties.

    [Category: Tags]  [Auth: V2]
    [Related: list_tags, create_tag, rename_tag]

    Args:
        name: The tag's internal name (from list_tags).
        color: New hex color.
        parent: New parent tag. Pass "" to remove parent.
        sort_type: "project", "dueDate", "title", or "priority".
        sort_order: Numeric sort order.
    """
    try:
        tag: dict = {"name": name}
        if color is not None:      tag["color"] = color
        if parent is not None:     tag["parent"] = parent
        if sort_type is not None:  tag["sortType"] = sort_type
        if sort_order is not None: tag["sortOrder"] = sort_order
        result = client.batch_tags(update=[tag])
        return result if isinstance(result, dict) else {"result": result}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def rename_tag(old_name: str, new_name: str) -> dict:
    """
    Rename a tag. All tasks using it are updated automatically.

    [Category: Tags]  [Auth: V2]
    [Related: list_tags, merge_tags]

    Args:
        old_name: Current tag name.
        new_name: New tag name.
    """
    try:
        result = client.rename_tag(old_name, new_name)
        return result if isinstance(result, dict) else {"success": True}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def merge_tags(source_name: str, target_name: str) -> dict:
    """
    Merge one tag into another. Tasks with source get target instead; source is deleted.

    [Category: Tags]  [Auth: V2]
    [Related: list_tags, rename_tag, delete_tag]

    Args:
        source_name: Tag to merge FROM (will be deleted).
        target_name: Tag to merge INTO (will remain).
    """
    try:
        result = client.merge_tags(source_name, target_name)
        return result if isinstance(result, dict) else {"success": True}
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def delete_tag(tag_name: str) -> dict:
    """
    Delete a tag. Removes it from all tasks.

    [Category: Tags]  [Auth: V2]
    [Related: list_tags, merge_tags]

    Args:
        tag_name: The tag name to delete.
    """
    try:
        result = client.delete_tag(tag_name)
        return result if isinstance(result, dict) else {"success": True, "deleted_tag": tag_name}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  🔁 HABITS (V2)
# ═══════════════════════════════════════════════════════════════════════════════

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
    Update an existing habit. Only provided fields are changed.

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
        reminders: New reminder times, e.g. ["08:00"].
        encouragement: New completion message.
        target_days: New target days.

    Common uses:
        Archive:  update_habit(habit_id="...", status=2)
        Rename:   update_habit(habit_id="...", name="New Name")
    """
    try:
        habit: dict = {"id": habit_id}
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

@mcp.tool()
def get_focus_stats(
    from_date: str,
    to_date: str,
    stat_type: str = "heatmap",
) -> dict:
    """
    Get focus/pomodoro statistics for a date range.

    [Category: Focus / Pomodoro]  [Auth: V2]
    [Related: get_productivity_stats]

    Args:
        from_date: Start date YYYYMMDD, e.g. "20260101".
        to_date: End date YYYYMMDD, e.g. "20260306".
        stat_type: "heatmap" (daily durations) or "distribution" (per-tag breakdown).

    Returns:
        heatmap: List of {date, duration} entries.
        distribution: {"tagDurations": {"tag_name": seconds, ...}}
    """
    try:
        if stat_type == "distribution":
            result = client.get_focus_distribution(from_date, to_date)
        else:
            result = client.get_focus_heatmap(from_date, to_date)
        return result if isinstance(result, dict) else {"data": result}
    except TickTickAPIError as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  👤 USER & PRODUCTIVITY (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_user_status() -> dict:
    """
    Get account status — inbox ID, Pro subscription, team membership.

    [Category: User & Stats]  [Auth: V2]
    [Related: get_productivity_stats, full_sync]

    Returns: userId, username, inboxId, pro, proStartDate, proEndDate, teamUser, etc.
    """
    try:
        return client.get_user_status().model_dump(exclude_none=False)
    except TickTickAPIError as e:
        return _err(e)


@mcp.tool()
def get_productivity_stats() -> dict:
    """
    Get productivity statistics — score, level, streaks, completion counts.

    [Category: User & Stats]  [Auth: V2]
    [Related: get_user_status, get_completed_tasks, get_focus_stats]

    Returns: score, level, completedToday, completedYesterday, completedThisWeek,
             completedThisMonth, currentStreak, maxStreak.
    """
    try:
        return client.get_productivity_stats()
    except TickTickAPIError as e:
        return _err(e)
