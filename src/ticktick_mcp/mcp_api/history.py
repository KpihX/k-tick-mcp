"""Completed and deleted task history MCP tools."""
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
