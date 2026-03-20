"""Batch and structural task MCP tools."""
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
def batch_create_tasks(tasks: list[dict]) -> dict:
    """
    Create multiple tasks at once via V2 batch.

    [Category: Tasks — Batch]  [Auth: V2]
    [Related: create_task, batch_update_tasks, batch_delete_tasks]

    ⚠️ SUBTASK TRAP — parentId in the task dict is SILENTLY IGNORED here too (V2 batch).
    Do NOT pass parentId expecting subtask relationships to be created automatically.
    ALWAYS call set_subtask_parent for each child AFTER this call.

    Args:
        tasks: List of task dicts. Each needs at least {"title": "..."}.
            Optional: projectId, content, priority, dueDate, startDate,
            timeZone, tags, allDay, kind, items, columnId.
            ⚠️ Do NOT include parentId — use set_subtask_parent instead.

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

    ⚠️ REMINDER RELIABILITY — DO NOT USE THIS TOOL FOR REMINDER UPDATES:
    batch_update_tasks() uses the V2 batch endpoint which cannot reliably set reminders
    on existing tasks, for two compounding reasons:
      1. V2-created tasks may have dueDate invisible to V1 (null), breaking reminder anchoring.
      2. Reminder object format {"trigger": "TRIGGER:-P2DT0H0M0S"} is silently rejected by the
         V2 batch endpoint — no error returned, but reminders are never saved.
    PREFERRED PATTERN: use update_task() (V1) with explicit due_date + time_zone + reminder_minutes.
    See the "Add/update reminders" workflow in ticktick_guide(show_workflows=True).

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
    [Related: batch_update_tasks, list_projects, set_subtask_parent]

    ⚠️ ORPHAN TRAP — The V2 API moves tasks individually, never cascading to children.
    Moving a parent task leaves its subtasks stranded in the old project.
    The parent-child relationship (parentId/childIds) is preserved in the metadata,
    but TickTick won't display subtasks correctly if they're in a different project.

    This tool automatically detects and cascades to children:
    For each unique source project, it fetches the full project data once via
    /project/{id}/data (which correctly returns childIds, unlike /project/{id}/task/{id}).
    A {task_id: childIds} index is built per source project — O(1) API calls per project,
    not per task. Children are appended to the move batch automatically (same destination).
    The returned dict includes `cascaded_children` listing any auto-added child moves.

    Args:
        moves: List of {"taskId": "...", "fromProjectId": "...", "toProjectId": "..."}.
            Only provide parent tasks — children are fetched and moved automatically.
    """
    try:
        # Build a {project_id: {task_id: childIds}} index — one API call per unique
        # source project via /project/{id}/data (V1), which correctly returns childIds.
        # get_task() uses /project/{id}/task/{id} which does NOT return childIds.
        source_projects = {m["fromProjectId"] for m in moves}
        child_index: dict[str, dict[str, list[str]]] = {}
        for proj_id in source_projects:
            try:
                project_data = client.get_project_data(proj_id)
                child_index[proj_id] = {
                    t.id: (t.childIds or [])
                    for t in project_data.tasks
                    if t.id
                }
            except Exception:
                child_index[proj_id] = {}

        augmented = list(moves)
        cascaded: list[dict] = []

        for move in moves:
            task_id = move["taskId"]
            from_project = move["fromProjectId"]
            to_project = move["toProjectId"]
            child_ids = child_index.get(from_project, {}).get(task_id, [])

            for child_id in child_ids:
                child_move = {
                    "taskId": child_id,
                    "fromProjectId": from_project,
                    "toProjectId": to_project,
                }
                augmented.append(child_move)
                cascaded.append(child_move)

        result = client.move_tasks(augmented)
        out = result if isinstance(result, dict) else {"result": result}
        if cascaded:
            out["cascaded_children"] = cascaded
        return out
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
