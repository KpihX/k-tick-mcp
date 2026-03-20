"""Focus and productivity MCP tools."""
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
