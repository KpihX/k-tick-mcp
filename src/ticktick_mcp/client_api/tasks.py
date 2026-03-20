"""
Task, sync, batch, and history operations.
"""
from __future__ import annotations

from ..models import Task, SyncResponse, BatchResponse, TickTickAPIError
from .transport import _v1_get, _v1_post, _v1_delete, _v2_get, _v2_post

def get_task(project_id: str, task_id: str) -> Task:
    data = _v1_get(f"/project/{project_id}/task/{task_id}")
    return Task.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════════
#  V1 — Tasks (write)
# ═══════════════════════════════════════════════════════════════════════════════

def create_task(payload: dict) -> Task:
    """POST /task — payload must include at minimum {"title": ...}."""
    data = _v1_post("/task", payload)
    return Task.model_validate(data)


def update_task(task_id: str, payload: dict) -> Task:
    """POST /task/{taskId} — full object required (id + projectId in body)."""
    data = _v1_post(f"/task/{task_id}", payload)
    return Task.model_validate(data)


def update_task_fields(project_id: str, task_id: str, **fields) -> Task:
    """
    Read-modify-write helper: fetches the current task, applies only the
    provided keyword arguments, then pushes the full object back.

    Fields with value ``""`` are treated as **clear** requests.  Because the
    V1 API ignores ``null`` / absent keys for dates, clearing is done via a
    follow-up V2 partial POST when V2 auth is available.

    Example:
        update_task_fields("proj123", "task456", title="New title", priority=3)
    """
    # Map snake_case tool params → camelCase API fields
    _key_map = {
        "due_date":    "dueDate",
        "start_date":  "startDate",
        "time_zone":   "timeZone",
        "project_id":  "projectId",
        "repeat_flag": "repeatFlag",
        "all_day":     "allDay",
        "is_all_day":  "isAllDay",
        "sort_order":  "sortOrder",
        "column_id":   "columnId",
        "parent_id":   "parentId",
        "pinned_time": "pinnedTime",
    }

    # Separate SET fields from CLEAR fields
    set_fields: dict = {}
    clear_keys: list[str] = []      # camelCase API keys to null-out
    for k, v in fields.items():
        api_key = _key_map.get(k, k)
        if v == "":
            clear_keys.append(api_key)
        else:
            set_fields[k] = v

    # Phase 1 — V1 read-modify-write for SET fields
    result: Task | None = None
    if set_fields:
        current = get_task(project_id, task_id)
        payload = current.model_dump(exclude_none=True)
        for k, v in set_fields.items():
            api_key = _key_map.get(k, k)
            payload[api_key] = v
        result = update_task(task_id, payload)

    # Phase 2 — V2 partial POST for CLEAR fields (V1 ignores null for dates)
    if clear_keys:
        if has_v2_auth():
            clear_payload: dict = {"projectId": project_id}
            for api_key in clear_keys:
                clear_payload[api_key] = None
            data = _v2_call("post", f"/task/{task_id}", payload=clear_payload)
            result = Task.model_validate(data)
        elif result is None:
            # V2 not available — fall back to V1 best-effort (null may be ignored)
            current = get_task(project_id, task_id)
            payload = current.model_dump(exclude_none=True)
            for api_key in clear_keys:
                payload.pop(api_key, None)
            result = update_task(task_id, payload)

    if result is None:
        # Edge case: no fields to set and V2 unavailable for clearing
        result = get_task(project_id, task_id)

    return result


def complete_task_v1(project_id: str, task_id: str) -> None:
    """POST /project/{projectId}/task/{taskId}/complete — dedicated V1 endpoint."""
    _v1_post(f"/project/{project_id}/task/{task_id}/complete", {})


def complete_task(project_id: str, task_id: str) -> Task:
    """Mark a task as completed. Uses V1 dedicated endpoint then re-fetches."""
    complete_task_v1(project_id, task_id)
    # Re-fetch to return the updated task
    try:
        return get_task(project_id, task_id)
    except TickTickAPIError:
        # If re-fetch fails (completed tasks may not be accessible via V1 GET),
        # return a minimal task object
        return Task(id=task_id, projectId=project_id, status=2)


def reopen_task(project_id: str, task_id: str) -> Task:
    """Reopen a completed task (status=0)."""
    return update_task_fields(project_id, task_id, status=0)


def delete_task(project_id: str, task_id: str) -> None:
    """DELETE /project/{projectId}/task/{taskId}. Irreversible."""
    _v1_delete(f"/project/{project_id}/task/{task_id}")


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Sync (full state dump)
# ═══════════════════════════════════════════════════════════════════════════════

def sync_all() -> SyncResponse:
    """GET /batch/check/0 — full state dump (all tasks, projects, tags, folders)."""
    data = _v2_get("/batch/check/0")
    return SyncResponse.model_validate(data)


def get_all_tasks() -> list[Task]:
    """Get ALL active tasks across all projects via V2 sync."""
    sync = sync_all()
    if sync.syncTaskBean:
        return sync.syncTaskBean.update
    return []


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Batch Task Operations
# ═══════════════════════════════════════════════════════════════════════════════

def batch_tasks(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[dict] | None = None,
) -> BatchResponse:
    """POST /batch/task — create, update, delete tasks in batch."""
    payload = {
        "add": add or [],
        "update": update or [],
        "delete": delete or [],
        "addAttachments": [],
        "updateAttachments": [],
        "deleteAttachments": [],
    }
    data = _v2_post("/batch/task", payload)
    return BatchResponse.model_validate(data)


def move_tasks(moves: list[dict]) -> dict | list:
    """POST /batch/taskProject — move tasks between projects.
    Each move: {"taskId": ..., "fromProjectId": ..., "toProjectId": ...}
    """
    return _v2_post("/batch/taskProject", moves)


def set_task_parent(relationships: list[dict]) -> dict | list:
    """POST /batch/taskParent — set/unset subtask relationships.
    Set:   [{"taskId": "child", "projectId": "proj", "parentId": "parent"}]
    Unset: [{"taskId": "child", "projectId": "proj", "oldParentId": "parent"}]
    """
    return _v2_post("/batch/taskParent", relationships)


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Completed / Deleted Tasks
# ═══════════════════════════════════════════════════════════════════════════════

def get_completed_tasks(
    from_date: str,
    to_date: str,
    status: str = "Completed",
    limit: int = 100,
) -> list[Task]:
    """GET /project/all/closed — completed or abandoned tasks.

    Args:
        from_date: "yyyy-MM-dd HH:mm:ss"
        to_date: "yyyy-MM-dd HH:mm:ss"
        status: "Completed" or "Abandoned"
        limit: max results (default 100)
    """
    params = {"from": from_date, "to": to_date, "status": status, "limit": limit}
    data = _v2_get("/project/all/closed", params=params)
    if isinstance(data, list):
        return [Task.model_validate(t) for t in data]
    return []


def get_deleted_tasks(start: int = 0, limit: int = 500) -> list[Task]:
    """GET /project/all/trash/pagination — deleted tasks (trash)."""
    params = {"start": start, "limit": limit}
    data = _v2_get("/project/all/trash/pagination", params=params)
    if isinstance(data, list):
        return [Task.model_validate(t) for t in data]
    # Sometimes returns {"tasks": [...]}
    if isinstance(data, dict) and "tasks" in data:
        return [Task.model_validate(t) for t in data["tasks"]]
    return []

__all__ = [
    'get_task', 'create_task', 'update_task', 'update_task_fields', 'complete_task_v1',
    'complete_task', 'reopen_task', 'delete_task', 'sync_all', 'get_all_tasks',
    'batch_tasks', 'move_tasks', 'set_task_parent', 'get_completed_tasks', 'get_deleted_tasks',
]
