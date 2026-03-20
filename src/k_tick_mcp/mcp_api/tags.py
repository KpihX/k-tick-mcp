"""Tag MCP tools."""
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
