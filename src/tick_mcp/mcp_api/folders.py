"""Folder and column MCP tools."""
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
