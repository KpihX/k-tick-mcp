"""Task read MCP tools."""
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
