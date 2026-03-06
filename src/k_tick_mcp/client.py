"""
TickTick API client — V1 (Official) + V2 (Unofficial) dual-stack.

V1 endpoints use OAuth2 Bearer token (TICKTICK_API_TOKEN).
V2 endpoints use session cookie (TICKTICK_SESSION_TOKEN) — optional.

All functions are synchronous (FastMCP handles the async layer).
Every response is validated through Pydantic models.
All errors are surfaced as TickTickAPIError with a clear status code.
"""
from __future__ import annotations

import httpx

from .config import (
    API_V1_BASE_URL, API_V2_BASE_URL, API_TIMEOUT,
    V2_SIGNON_URL, SIGNON_PARAMS, V2_LOGIN_HEADERS, SESSION_COOKIE_NAME,
    USER_AGENT, V2_DEVICE_HEADER,
    ENV_API_TOKEN, ENV_SESSION_TOKEN, ENV_USERNAME, ENV_PASSWORD,
    get_api_token, get_session_token, get_username, get_password, has_v2_auth,
    refresh_session_from_vault, SessionTokenExpiredError,
)
from .models import (
    Task, Project, ProjectData, ProjectGroup, Column, Tag,
    Habit, HabitSection, UserStatus,
    SyncResponse, BatchResponse,
    TickTickAPIError,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Low-level HTTP
# ═══════════════════════════════════════════════════════════════════════════════

# ── V2 session token cache ────────────────────────────────────────────────────
# Module-level variable: survives for the lifetime of the MCP process.
# Initialised empty; populated lazily on the first V2 call.
_v2_session_token: str | None = None


def _v2_invalidate() -> None:
    """Clear the in-process V2 token cache (called before re-login on 401)."""
    global _v2_session_token
    _v2_session_token = None


def _v2_login() -> str:
    """
    Authenticate against the TickTick web API and cache the session token.

    POST /api/v2/user/signon?wc=true&remember=true
    Body : {"username": <email>, "password": <password>}
    Response includes a top-level "token" field — that is the V2 session cookie.

    Raises TickTickAPIError if credentials are missing or login fails.
    """
    global _v2_session_token
    username = get_username()
    password = get_password()
    if not username or not password:
        raise TickTickAPIError(
            0,
            "V2 auth unavailable. Provide either:\n"
            f"  • {ENV_SESSION_TOKEN} (session cookie from browser)\n"
            f"  • {ENV_USERNAME} + {ENV_PASSWORD} (auto-login)\n"
            "See .env.example for details."
        )
    with httpx.Client(timeout=API_TIMEOUT) as c:
        r = c.post(
            V2_SIGNON_URL,
            params=SIGNON_PARAMS,
            json={"username": username, "password": password},
            headers=V2_LOGIN_HEADERS,
        )
    if r.status_code != 200:
        raise TickTickAPIError(r.status_code, f"V2 login failed: {r.text[:200]}")
    data = r.json()
    token = data.get("token")
    if token:
        _v2_session_token = token
        return token
    # TickTick requires a verification code (device/2FA check)
    if data.get("authId"):
        raise TickTickAPIError(
            0,
            "V2 login requires a verification code (device check / 2FA).\n"
            "The automated flow cannot handle interactive prompts.\n"
            "Fix: run  ticktick-admin session refresh  in your terminal —\n"
            "  it will prompt for the code interactively and save the token."
        )
    raise TickTickAPIError(
        0, f"V2 login succeeded but response has no 'token' field. Keys: {list(data.keys())}"
    )


def _get_v2_token() -> str:
    """
    Return a valid V2 session token, resolving in this priority order:
      1. In-process cache (_v2_session_token) — fastest path
      2. TICKTICK_SESSION_TOKEN env var — loaded once at startup
      3. Auto-login via TICKTICK_USERNAME + TICKTICK_PASSWORD
    """
    global _v2_session_token
    if _v2_session_token:
        return _v2_session_token
    token = get_session_token()          # from env / .env file
    if token:
        _v2_session_token = token
        return token
    return _v2_login()                   # credentials-based auto-login


def _v1_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_api_token()}",
        "Content-Type": "application/json",
    }


def _v2_headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}={_get_v2_token()}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Device": V2_DEVICE_HEADER,
    }


def _require_v2() -> None:
    """Raise a clear error if V2 auth is not possible at all."""
    if not has_v2_auth():
        raise TickTickAPIError(
            0,
            "This feature requires V2 API access. Provide either:\n"
            f"  • {ENV_SESSION_TOKEN} (session cookie from browser)\n"
            f"  • {ENV_USERNAME} + {ENV_PASSWORD} (auto-login)\n"
            "See .env.example for details."
        )


def _v2_call(
    method: str,
    endpoint: str,
    *,
    params: dict | None = None,
    payload: dict | list | None = None,
) -> dict | list:
    """
    Execute a V2 HTTP request with automatic token refresh on 401.

    Flow:
      1. Try request with current token.
      2. If 401 → invalidate cache → re-login → retry ONCE.
      3. If still 401 → raise TickTickAPIError(401, ...).
    """
    url = f"{API_V2_BASE_URL}{endpoint}"

    def _do() -> httpx.Response:
        with httpx.Client(timeout=API_TIMEOUT) as c:
            kwargs: dict = {"headers": _v2_headers(), "params": params}
            if method in ("post", "put", "patch"):
                kwargs["json"] = payload
            return getattr(c, method)(url, **kwargs)

    tried: list[str] = []
    r = _do()
    if r.status_code == 401:
        tried.append("Initial request with cached/env token → 401")
        # ── Attempt 1: check if bw-env vault has a fresher token ──
        fresh = refresh_session_from_vault()
        if fresh:
            global _v2_session_token
            _v2_session_token = fresh
            tried.append("bw-env vault returned a NEW token → retrying")
            r = _do()
        else:
            tried.append("bw-env vault: same token or unavailable")
            # ── Attempt 2: fallback to credentials-based re-login ──
            _v2_invalidate()   # stale token → discard
            tried.append("Credentials re-login attempted")
            r = _do()          # re-login triggered via _get_v2_token → _v2_login
    if r.status_code == 401:
        raise SessionTokenExpiredError(tried=tried)
    return _handle(r)


def _handle(r: httpx.Response) -> dict | list:
    """Translate HTTP status codes into structured errors."""
    if r.status_code == 401:
        raise TickTickAPIError(
            401,
            f"V1 API token expired or invalid ({ENV_API_TOKEN}).\n"
            "Fix: run  ticktick-admin token set <new_token>  in your terminal,\n"
            "  or copy the token from TickTick → Settings → Integrations → API\n"
            "  and set it in src/k_tick_mcp/.env."
        )
    if r.status_code == 403:
        raise TickTickAPIError(403, "Forbidden — insufficient permissions for this resource.")
    if r.status_code == 404:
        raise TickTickAPIError(404, "Not found — check project_id and task_id.")
    if r.status_code == 429:
        raise TickTickAPIError(429, "Rate limit exceeded — wait a moment before retrying.")
    if r.status_code >= 500:
        raise TickTickAPIError(r.status_code, f"TickTick server error. Body: {r.text[:200]}")
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        raise TickTickAPIError(r.status_code, r.text[:300])
    # 204 No Content (DELETE) or empty response
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


# ── V1 HTTP helpers ───────────────────────────────────────────────────────────

def _v1_get(endpoint: str) -> dict | list:
    url = f"{API_V1_BASE_URL}{endpoint}"
    with httpx.Client(timeout=API_TIMEOUT) as c:
        return _handle(c.get(url, headers=_v1_headers()))


def _v1_post(endpoint: str, payload: dict) -> dict | list:
    url = f"{API_V1_BASE_URL}{endpoint}"
    with httpx.Client(timeout=API_TIMEOUT) as c:
        return _handle(c.post(url, json=payload, headers=_v1_headers()))


def _v1_delete(endpoint: str) -> None:
    url = f"{API_V1_BASE_URL}{endpoint}"
    with httpx.Client(timeout=API_TIMEOUT) as c:
        _handle(c.delete(url, headers=_v1_headers()))


# ── V2 HTTP helpers ───────────────────────────────────────────────────────────

def _v2_get(endpoint: str, params: dict | None = None) -> dict | list:
    _require_v2()
    return _v2_call("get", endpoint, params=params)


def _v2_post(endpoint: str, payload: dict | list | None = None) -> dict | list:
    _require_v2()
    return _v2_call("post", endpoint, payload=payload)


def _v2_put(endpoint: str, payload: dict | None = None) -> dict | list:
    _require_v2()
    return _v2_call("put", endpoint, payload=payload)


def _v2_delete(endpoint: str, params: dict | None = None) -> dict | list:
    _require_v2()
    return _v2_call("delete", endpoint, params=params)


# ═══════════════════════════════════════════════════════════════════════════════
#  V1 — Projects
# ═══════════════════════════════════════════════════════════════════════════════

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
    """POST /project/{projectId} — full or partial project object."""
    data = _v1_post(f"/project/{project_id}", payload)
    return Project.model_validate(data)


def delete_project(project_id: str) -> None:
    """DELETE /project/{projectId}. Irreversible."""
    _v1_delete(f"/project/{project_id}")


# ═══════════════════════════════════════════════════════════════════════════════
#  V1 — Tasks (read)
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Project Folders/Groups
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


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Habits
# ═══════════════════════════════════════════════════════════════════════════════

def get_habits() -> list[Habit]:
    """GET /habits — list all habits."""
    data = _v2_get("/habits")
    if isinstance(data, list):
        return [Habit.model_validate(h) for h in data]
    return []


def get_habit_sections() -> list[HabitSection]:
    """GET /habitSections — list habit sections (morning/afternoon/night)."""
    data = _v2_get("/habitSections")
    if isinstance(data, list):
        return [HabitSection.model_validate(s) for s in data]
    return []


def batch_habits(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[str] | None = None,
) -> dict | list:
    """POST /habits/batch — create, update, delete habits."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/habits/batch", payload)


def query_habit_checkins(habit_ids: list[str], after_stamp: int = 0) -> dict:
    """POST /habitCheckins/query — get check-in records for habits.

    Args:
        habit_ids: List of habit IDs to query.
        after_stamp: YYYYMMDD integer. 0 = all history.

    Returns dict: {"checkins": {"habitId": [HabitCheckin, ...]}}
    """
    payload = {"habitIds": habit_ids, "afterStamp": after_stamp}
    data = _v2_post("/habitCheckins/query", payload)
    return data if isinstance(data, dict) else {}


def batch_habit_checkins(
    add: list[dict] | None = None,
    update: list[dict] | None = None,
    delete: list[str] | None = None,
) -> dict | list:
    """POST /habitCheckins/batch — create, update, delete check-ins."""
    payload = {"add": add or [], "update": update or [], "delete": delete or []}
    return _v2_post("/habitCheckins/batch", payload)


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — Focus / Pomodoro
# ═══════════════════════════════════════════════════════════════════════════════

def get_focus_heatmap(from_date: str, to_date: str) -> dict | list:
    """GET /pomodoros/statistics/heatmap/{from}/{to}.
    Dates in YYYYMMDD format.
    """
    return _v2_get(f"/pomodoros/statistics/heatmap/{from_date}/{to_date}")


def get_focus_distribution(from_date: str, to_date: str) -> dict | list:
    """GET /pomodoros/statistics/dist/{from}/{to}.
    Dates in YYYYMMDD format.
    Returns {"tagDurations": {"tag_name": seconds, ...}}
    """
    return _v2_get(f"/pomodoros/statistics/dist/{from_date}/{to_date}")


# ═══════════════════════════════════════════════════════════════════════════════
#  V2 — User & Statistics
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_status() -> UserStatus:
    """GET /user/status — account status, inbox ID, pro subscription."""
    data = _v2_get("/user/status")
    return UserStatus.model_validate(data)


def get_user_profile() -> dict:
    """GET /user/profile — user profile data."""
    data = _v2_get("/user/profile")
    return data if isinstance(data, dict) else {}


def get_user_preferences() -> dict:
    """GET /user/preferences/settings — user preferences."""
    data = _v2_get("/user/preferences/settings", params={"includeWeb": "true"})
    return data if isinstance(data, dict) else {}


def get_productivity_stats() -> dict:
    """GET /statistics/general — productivity statistics (score, level, streaks)."""
    data = _v2_get("/statistics/general")
    return data if isinstance(data, dict) else {}