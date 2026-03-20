"""
Project, folder, column, and tag operations.
"""
from __future__ import annotations

from ..models import Project, ProjectData, ProjectGroup, Column, Tag, TickTickAPIError
from .transport import _v1_get, _v1_post, _v1_delete, _v2_get, _v2_post, _v2_put, _v2_delete
from .tasks import sync_all

def get_projects() -> list[Project]:
    data = _v1_get("/project")
    if not isinstance(data, list):
        raise TickTickAPIError(0, f"Unexpected response shape: {type(data)}")
    return [Project.model_validate(p) for p in data]


def get_project(project_id: str) -> Project:
    data = _v1_get(f"/project/{project_id}")
    return Project.model_validate(data)


def get_inbox_data() -> ProjectData:
    data = _v1_get("/project/inbox/data")
    return ProjectData.model_validate(data)


def get_project_data(project_id: str) -> ProjectData:
    data = _v1_get(f"/project/{project_id}/data")
    return ProjectData.model_validate(data)


def create_project(payload: dict) -> Project:
    """POST /project — payload must include at minimum {"name": ...}."""
    data = _v1_post("/project", payload)
    return Project.model_validate(data)


def update_project(project_id: str, payload: dict) -> Project:
    """POST /project/{projectId} — full or partial project object.

    ⚠️  V1 limitation: the `groupId` field is silently ignored by this
    endpoint. Use batch_projects() (V2) to persist folder assignments.
    The response also always returns groupId=null even when set via V2.
    """
    data = _v1_post(f"/project/{project_id}", payload)
    return Project.model_validate(data)


def delete_project(project_id: str) -> None:
    """DELETE /project/{projectId}. Irreversible."""
    _v1_delete(f"/project/{project_id}")


# ═══════════════════════════════════════════════════════════════════════════════
#  V1 — Tasks (read)
# ═══════════════════════════════════════════════════════════════════════════════

def get_project_groups() -> list[ProjectGroup]:
    """Get all project groups/folders via sync."""
    sync = sync_all()
    return sync.projectGroups


def batch_project_groups(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[str] | None = None,
) -> dict | list:
    """POST /batch/projectGroup — create, update, delete project folders."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/batch/projectGroup", payload)


def batch_projects(update: list[dict]) -> dict:
    """POST /batch/project — update project fields via V2 (supports groupId).

    ⚠️  REPLACE semantics: the API treats the payload as a partial REPLACE.
    Fields NOT included in each item dict may be wiped (notably `name`).
    Always include all critical fields (id, name, kind, color, groupId, …)
    by doing a read-modify-write before calling this function.

    The V1 update_project endpoint silently ignores groupId — use this
    function when folder assignment (groupId) must actually persist.

    Args:
        update: List of project dicts. Each MUST include:
            - "id": project ID
            - "name": project name  ← required; omitting it will null the name
            Recommended: also include kind, color, viewMode, sortOrder.

    Returns: {"id2etag": {projectId: etag}, "id2error": {projectId: error}}.
    Check id2error before assuming success.
    """
    return _v2_post("/batch/project", {"update": update})


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Kanban Columns
# ═══════════════════════════════════════════════════════════════════════════════

def get_columns(project_id: str) -> list[Column]:
    """GET /column/project/{projectId} — list kanban columns."""
    data = _v2_get(f"/column/project/{project_id}")
    if isinstance(data, list):
        return [Column.model_validate(c) for c in data]
    return []


def batch_columns(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[dict] | None = None,
) -> dict | list:
    """POST /column — create, update, delete kanban columns."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/column", payload)


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Tags
# ═══════════════════════════════════════════════════════════════════════════════

def get_tags() -> list[Tag]:
    """Get all tags via sync."""
    sync = sync_all()
    return sync.tags


def batch_tags(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
) -> dict | list:
    """POST /batch/tag — create or update tags."""
    payload = {"add": add or [], "update": update or []}
    return _v2_post("/batch/tag", payload)


def rename_tag(old_name: str, new_name: str) -> dict | list:
    """PUT /tag/rename — rename a tag."""
    return _v2_put("/tag/rename", {"name": old_name, "newName": new_name})


def merge_tags(source_name: str, target_name: str) -> dict | list:
    """PUT /tag/merge — merge source tag into target tag."""
    return _v2_put("/tag/merge", {"name": source_name, "newName": target_name})


def delete_tag(tag_name: str) -> dict | list:
    """DELETE /tag?name={tagName} — delete a tag."""
    return _v2_delete("/tag", params={"name": tag_name})


def get_project_raw(project_id: str) -> dict:
    """Return the raw V1 project payload without pydantic normalization."""
    data = _v1_get(f"/project/{project_id}")
    return data if isinstance(data, dict) else {}

__all__ = [
    'get_projects', 'get_project', 'get_project_raw', 'get_inbox_data', 'get_project_data',
    'create_project', 'update_project', 'delete_project', 'get_project_groups',
    'batch_project_groups', 'batch_projects', 'get_columns', 'batch_columns',
    'get_tags', 'batch_tags', 'rename_tag', 'merge_tags', 'delete_tag',
]
