"""Task write MCP tools."""
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

    ⚠️ SUBTASK TRAP — parentId is SILENTLY IGNORED by the V1 creation endpoint.
    Passing parentId in the payload creates a standalone task with no error or warning.
    ALWAYS use set_subtask_parent AFTER creation to establish the relationship.
    Correct sequence: create_task (parent) → create_task / batch_create_tasks (children) → set_subtask_parent × N

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
            ⚠️ V1/V2 GOTCHA — REMINDER ANCHOR REQUIRED:
            Tasks created via V2 batch may have dueDate invisible to V1 (returns null).
            V1 uses dueDate as the anchor to compute reminder trigger offsets (TRIGGER:-P2D).
            If due_date is null, reminder_minutes is silently ignored — no error, no reminder.
            FIX: ALWAYS pass due_date + time_zone explicitly alongside reminder_minutes,
            even if you are not changing the due date. Read the existing due date from
            get_task_detail() first, then pass it through. Example:
                update_task(task_id='...', project_id='...', due_date='2026-06-03T21:00:00+0000',
                            time_zone='Europe/Paris', reminder_minutes=[2880, 1440])
            Returns reminders: ['TRIGGER:-P2D', 'TRIGGER:-P1D'] when correctly anchored.
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
