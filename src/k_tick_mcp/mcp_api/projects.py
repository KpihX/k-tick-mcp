"""Project MCP tools."""
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
def list_projects() -> list[dict]:
    """
    List all TickTick projects (lists).

    [Category: Projects]  [Auth: V1]
    [Related: get_project_detail, create_project, get_project_tasks, list_project_folders]

    Returns: id, name, kind (TASK/NOTE), closed, color, sortOrder, groupId.
    Use the returned 'id' as project_id in task tools.

    ⚠️  V1 limitation: groupId is ALWAYS null in V1 responses, even when a
    folder assignment exists. Use full_sync() to see real groupId values.
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

    [Category: Projects]  [Auth: V1 + V2 when group_id is provided]
    [Related: list_projects, update_project, delete_project, list_project_folders]
    [Workflow: Create project → manage_columns (for kanban) → create_task]

    Args:
        name: Project name (required).
        color: Hex color, e.g. "#F18181".
        kind: "TASK" (default) or "NOTE".
        view_mode: "list", "kanban", or "timeline".
        group_id: Folder ID to file project in (from list_project_folders).

    ⚠️  group_id ALWAYS requires a V2 follow-up — handled automatically here:
        The V1 create endpoint silently ignores groupId in the payload (no error,
        no warning — it just doesn't persist). This tool works around it by:
        1. Creating the project via V1 to obtain the new project ID.
        2. Immediately calling V2 POST /batch/project to assign the groupId.
        The returned dict reflects groupId correctly. Verify with full_sync()
        if needed — V1 list_projects always shows groupId=null regardless.

    ⚠️  Never try to assign group_id via a raw V1 update — it silently fails.
        Always go through update_project(group_id=...) which also uses V2.
    """
    try:
        payload: dict = {"name": name, "kind": kind}
        if color:     payload["color"] = color
        if view_mode: payload["viewMode"] = view_mode
        created = client.create_project(payload).model_dump(exclude_none=False)

        if group_id:
            # V1 silently ignores groupId — assign via V2 batch right after creation.
            v2_item: dict = {k: v for k, v in created.items() if v is not None}
            v2_item["id"] = created["id"]
            v2_item["groupId"] = group_id
            v2_item["name"] = name
            v2_item["kind"] = kind
            if view_mode: v2_item["viewMode"] = view_mode
            result = client.batch_projects([v2_item])
            errors = result.get("id2error", {}) if isinstance(result, dict) else {}
            if errors:
                return {
                    "error": True,
                    "status_code": 0,
                    "message": f"Project created (id={created['id']}) but groupId assignment failed: {errors}",
                    "project": created,
                }
            created["groupId"] = group_id  # reflect real state in response

        return created
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

    [Category: Projects]  [Auth: V1 / V2 when group_id is provided]
    [Related: get_project_detail, create_project, delete_project, list_project_folders]

    Args:
        project_id: The project to update.
        name: New name.
        color: Hex color.
        kind: "TASK" or "NOTE".
        view_mode: "list", "kanban", or "timeline".
        group_id: Move to a different folder (from list_project_folders).
        closed: True=archive, False=unarchive.

    ⚠️  group_id uses V2 internally (read-modify-write):
        The V1 update endpoint silently ignores groupId. When group_id is
        provided, this tool fetches the current project state first, then
        applies all changes via V2 POST /batch/project so no other fields
        (name, color, kind, …) are accidentally wiped.

    ⚠️  V1 responses always return groupId=null:
        After a successful folder assignment, V1 get_project_detail still
        shows groupId=null. Use full_sync() to verify the real value via V2.
    """
    try:
        payload: dict = {}
        if name is not None:      payload["name"] = name
        if color is not None:     payload["color"] = color
        if kind is not None:      payload["kind"] = kind
        if view_mode is not None: payload["viewMode"] = view_mode
        if closed is not None:    payload["closed"] = closed
        if not payload and group_id is None:
            return {"error": True, "status_code": 0, "message": "No fields provided."}

        if group_id is not None:
            # V1 silently ignores groupId — use V2 batch/project with read-modify-write.
            # Fetch current raw state so no existing fields (name, color, …) are wiped.
            current_raw = client.get_project_raw(project_id)
            v2_item: dict = {k: v for k, v in current_raw.items() if v is not None}
            v2_item["id"] = project_id
            v2_item["groupId"] = group_id
            v2_item.update(payload)           # apply caller-supplied overrides
            result = client.batch_projects([v2_item])
            errors = result.get("id2error", {})
            if errors:
                return {"error": True, "status_code": 0, "message": str(errors)}
            # Re-fetch raw and return (V1 shape — groupId will show null, expected)
            return client.get_project_raw(project_id)

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
