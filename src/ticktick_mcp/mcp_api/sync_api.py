"""Sync MCP tools."""
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
