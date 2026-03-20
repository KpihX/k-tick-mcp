"""
Tests for tick_mcp.client — dual V1/V2 HTTP stack.

Markers:
  @unit — mocked HTTP via respx, no real network.
  @live — hit the real TickTick API (opt-in via `pytest -m live`).
"""
from __future__ import annotations

import pytest
import httpx
import respx

import tick_mcp.client as client_mod
from tick_mcp.client import (
    _handle,
    _v1_headers,
    _v2_headers,
    _v2_invalidate,
    _get_v2_token,
    _v2_call,
    _v2_login,
    _require_v2,
    # V1 functions
    get_projects,
    get_project,
    get_task,
    create_task,
    update_task,
    delete_task,
    complete_task,
    # V2 functions
    sync_all,
    get_all_tasks,
    batch_tasks,
    get_tags,
    get_habits,
    get_user_status,
)
from tick_mcp.models import (
    TickTickAPIError, Task, Project, SyncResponse, Tag, Habit, UserStatus,
)
from tick_mcp.config import SessionTokenExpiredError, V2_SIGNON_URL


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_v2_cache():
    """Ensure each test starts with a clean V2 token cache."""
    _v2_invalidate()
    yield
    _v2_invalidate()


@pytest.fixture()
def mock_tokens(monkeypatch):
    """Stub config getters so no real secrets are needed."""
    monkeypatch.setattr(client_mod, "get_api_token", lambda: "fake_api_token")
    monkeypatch.setattr(client_mod, "get_session_token", lambda: "fake_session_token")
    monkeypatch.setattr(client_mod, "has_v2_auth", lambda: True)
    monkeypatch.setattr(client_mod, "get_username", lambda: "user@example.com")
    monkeypatch.setattr(client_mod, "get_password", lambda: "pw")
    monkeypatch.setattr(client_mod, "refresh_session_from_vault", lambda: None)


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: _handle() — HTTP status translation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestHandle:
    def _make_response(self, status_code, json_body=None, content=b""):
        """Build a fake httpx.Response."""
        if json_body is not None:
            import json
            content = json.dumps(json_body).encode()
        return httpx.Response(
            status_code=status_code,
            content=content,
            request=httpx.Request("GET", "https://example.com"),
        )

    def test_200_json(self):
        r = self._make_response(200, {"id": "t1", "title": "Ok"})
        result = _handle(r)
        assert result == {"id": "t1", "title": "Ok"}

    def test_204_empty(self):
        r = self._make_response(204)
        result = _handle(r)
        assert result == {}

    def test_401_raises(self):
        r = self._make_response(401, content=b"Unauthorized")
        with pytest.raises(TickTickAPIError) as exc_info:
            _handle(r)
        assert exc_info.value.status_code == 401

    def test_403_raises(self):
        r = self._make_response(403, content=b"Forbidden")
        with pytest.raises(TickTickAPIError) as exc_info:
            _handle(r)
        assert exc_info.value.status_code == 403

    def test_404_raises(self):
        r = self._make_response(404, content=b"Not Found")
        with pytest.raises(TickTickAPIError) as exc_info:
            _handle(r)
        assert exc_info.value.status_code == 404

    def test_429_raises(self):
        r = self._make_response(429, content=b"Rate limited")
        with pytest.raises(TickTickAPIError) as exc_info:
            _handle(r)
        assert exc_info.value.status_code == 429

    def test_500_raises(self):
        r = self._make_response(500, content=b"Server Error")
        with pytest.raises(TickTickAPIError) as exc_info:
            _handle(r)
        assert exc_info.value.status_code == 500

    def test_200_list(self):
        r = self._make_response(200, [{"id": 1}, {"id": 2}])
        result = _handle(r)
        assert isinstance(result, list)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: Header construction
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestHeaders:
    def test_v1_headers_has_bearer(self, mock_tokens):
        h = _v1_headers()
        assert h["Authorization"] == "Bearer fake_api_token"
        assert h["Content-Type"] == "application/json"

    def test_v2_headers_has_cookie(self, mock_tokens):
        h = _v2_headers()
        assert "t=fake_session_token" in h["Cookie"]
        assert "X-Device" in h


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: _get_v2_token() resolution chain
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestGetV2Token:
    def test_uses_cached_token(self, mock_tokens):
        """If _v2_session_token is set, use it directly."""
        client_mod._v2_session_token = "cached_token"
        assert _get_v2_token() == "cached_token"

    def test_falls_back_to_config(self, mock_tokens):
        """If cache is empty, use get_session_token()."""
        token = _get_v2_token()
        assert token == "fake_session_token"

    def test_falls_back_to_login(self, monkeypatch):
        """If both cache and config are empty, call _v2_login()."""
        monkeypatch.setattr(client_mod, "get_session_token", lambda: None)
        monkeypatch.setattr(client_mod, "_v2_login", lambda: "login_token")
        token = _get_v2_token()
        assert token == "login_token"


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: _require_v2()
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRequireV2:
    def test_passes_when_auth_available(self, mock_tokens):
        _require_v2()  # should not raise

    def test_raises_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(client_mod, "has_v2_auth", lambda: False)
        with pytest.raises(TickTickAPIError) as exc_info:
            _require_v2()
        assert "V2 API access" in exc_info.value.message


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: V1 endpoints (mocked via respx)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestV1Endpoints:
    @respx.mock
    def test_get_projects(self, mock_tokens):
        route = respx.get("https://api.ticktick.com/open/v1/project").mock(
            return_value=httpx.Response(200, json=[
                {"id": "p1", "name": "Work"},
                {"id": "p2", "name": "Personal"},
            ])
        )
        projects = get_projects()
        assert len(projects) == 2
        assert all(isinstance(p, Project) for p in projects)
        assert projects[0].name == "Work"

    @respx.mock
    def test_get_project(self, mock_tokens):
        respx.get("https://api.ticktick.com/open/v1/project/p1").mock(
            return_value=httpx.Response(200, json={"id": "p1", "name": "Work"})
        )
        project = get_project("p1")
        assert project.id == "p1"

    @respx.mock
    def test_get_task(self, mock_tokens):
        respx.get("https://api.ticktick.com/open/v1/project/p1/task/t1").mock(
            return_value=httpx.Response(200, json={
                "id": "t1", "projectId": "p1", "title": "Test task",
            })
        )
        task = get_task("p1", "t1")
        assert isinstance(task, Task)
        assert task.title == "Test task"

    @respx.mock
    def test_create_task(self, mock_tokens):
        respx.post("https://api.ticktick.com/open/v1/task").mock(
            return_value=httpx.Response(200, json={
                "id": "new1", "projectId": "p1", "title": "Buy milk",
            })
        )
        task = create_task({"title": "Buy milk", "projectId": "p1"})
        assert task.id == "new1"
        assert task.title == "Buy milk"

    @respx.mock
    def test_update_task(self, mock_tokens):
        respx.post("https://api.ticktick.com/open/v1/task/t1").mock(
            return_value=httpx.Response(200, json={
                "id": "t1", "projectId": "p1", "title": "Updated",
            })
        )
        task = update_task("t1", {"id": "t1", "projectId": "p1", "title": "Updated"})
        assert task.title == "Updated"

    @respx.mock
    def test_delete_task(self, mock_tokens):
        respx.delete("https://api.ticktick.com/open/v1/project/p1/task/t1").mock(
            return_value=httpx.Response(204)
        )
        delete_task("p1", "t1")  # should not raise

    @respx.mock
    def test_complete_task(self, mock_tokens):
        respx.post("https://api.ticktick.com/open/v1/project/p1/task/t1/complete").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.get("https://api.ticktick.com/open/v1/project/p1/task/t1").mock(
            return_value=httpx.Response(200, json={
                "id": "t1", "projectId": "p1", "title": "Done", "status": 2,
            })
        )
        task = complete_task("p1", "t1")
        assert task.is_completed()

    @respx.mock
    def test_get_projects_404(self, mock_tokens):
        respx.get("https://api.ticktick.com/open/v1/project").mock(
            return_value=httpx.Response(404, content=b"Not Found")
        )
        with pytest.raises(TickTickAPIError) as exc_info:
            get_projects()
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: V2 endpoints (mocked via respx)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestV2Endpoints:
    @respx.mock
    def test_sync_all(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/batch/check/0").mock(
            return_value=httpx.Response(200, json={
                "syncTaskBean": {"update": [{"title": "T1", "id": "t1", "projectId": "p1"}]},
                "projectProfiles": [{"id": "p1", "name": "Inbox"}],
                "tags": [{"name": "work"}],
            })
        )
        sync = sync_all()
        assert isinstance(sync, SyncResponse)
        assert len(sync.tags) == 1
        assert sync.syncTaskBean.update[0].title == "T1"

    @respx.mock
    def test_get_all_tasks(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/batch/check/0").mock(
            return_value=httpx.Response(200, json={
                "syncTaskBean": {
                    "update": [
                        {"title": "A", "id": "1", "projectId": "p1"},
                        {"title": "B", "id": "2", "projectId": "p1"},
                    ]
                },
            })
        )
        tasks = get_all_tasks()
        assert len(tasks) == 2
        assert all(isinstance(t, Task) for t in tasks)

    @respx.mock
    def test_get_all_tasks_empty(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/batch/check/0").mock(
            return_value=httpx.Response(200, json={})
        )
        tasks = get_all_tasks()
        assert tasks == []

    @respx.mock
    def test_get_tags(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/batch/check/0").mock(
            return_value=httpx.Response(200, json={
                "tags": [
                    {"name": "urgent", "color": "#ff0000"},
                    {"name": "work"},
                ],
            })
        )
        tags = get_tags()
        assert len(tags) == 2
        assert all(isinstance(t, Tag) for t in tags)

    @respx.mock
    def test_get_habits(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/habits").mock(
            return_value=httpx.Response(200, json=[
                {"name": "Meditate", "id": "h1"},
            ])
        )
        habits = get_habits()
        assert len(habits) == 1
        assert isinstance(habits[0], Habit)

    @respx.mock
    def test_get_user_status(self, mock_tokens):
        respx.get("https://api.ticktick.com/api/v2/user/status").mock(
            return_value=httpx.Response(200, json={
                "userId": 123, "username": "test", "pro": True,
            })
        )
        status = get_user_status()
        assert isinstance(status, UserStatus)
        assert status.pro is True

    @respx.mock
    def test_batch_tasks(self, mock_tokens):
        respx.post("https://api.ticktick.com/api/v2/batch/task").mock(
            return_value=httpx.Response(200, json={
                "id2etag": {"t1": "etag1"},
                "id2error": {},
            })
        )
        result = batch_tasks(
            add=[{"title": "New task", "projectId": "p1"}],
        )
        assert "t1" in result.id2etag


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: V2 401 retry logic
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestV2RetryLogic:
    @respx.mock
    def test_401_then_vault_refresh_succeeds(self, mock_tokens, monkeypatch):
        """First request 401 → vault has fresh token → retry succeeds."""
        call_count = {"n": 0}

        def _route_handler(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return httpx.Response(401, content=b"Expired")
            return httpx.Response(200, json={"ok": True})

        respx.get("https://api.ticktick.com/api/v2/test").mock(side_effect=_route_handler)
        monkeypatch.setattr(client_mod, "refresh_session_from_vault", lambda: "fresh_token")

        result = _v2_call("get", "/test")
        assert result == {"ok": True}
        assert call_count["n"] == 2

    @respx.mock
    def test_401_vault_same_then_relogin(self, mock_tokens, monkeypatch):
        """401 → vault same → credentials re-login → success."""
        call_count = {"n": 0}

        def _route_handler(request):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return httpx.Response(401, content=b"Expired")
            return httpx.Response(200, json={"ok": True})

        respx.get("https://api.ticktick.com/api/v2/test").mock(side_effect=_route_handler)
        monkeypatch.setattr(client_mod, "refresh_session_from_vault", lambda: None)
        # _v2_login won't be called directly; _get_v2_token falls back after invalidate
        monkeypatch.setattr(client_mod, "_v2_login", lambda: "relogin_token")

        result = _v2_call("get", "/test")
        assert result == {"ok": True}

    @respx.mock
    def test_401_all_retries_fail_raises(self, mock_tokens, monkeypatch):
        """401 on every attempt → SessionTokenExpiredError."""
        respx.get("https://api.ticktick.com/api/v2/test").mock(
            return_value=httpx.Response(401, content=b"Expired")
        )
        monkeypatch.setattr(client_mod, "refresh_session_from_vault", lambda: None)
        monkeypatch.setattr(client_mod, "_v2_login", lambda: "still_bad")

        with pytest.raises(SessionTokenExpiredError):
            _v2_call("get", "/test")


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit: V2 login flow
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestV2Login:
    @respx.mock
    def test_login_success(self, monkeypatch):
        monkeypatch.setattr(client_mod, "get_username", lambda: "user@test.com")
        monkeypatch.setattr(client_mod, "get_password", lambda: "pass123")
        respx.post(V2_SIGNON_URL).mock(
            return_value=httpx.Response(200, json={"token": "new_session"})
        )
        token = _v2_login()
        assert token == "new_session"

    @respx.mock
    def test_login_no_credentials(self, monkeypatch):
        monkeypatch.setattr(client_mod, "get_username", lambda: None)
        monkeypatch.setattr(client_mod, "get_password", lambda: None)
        with pytest.raises(TickTickAPIError) as exc_info:
            _v2_login()
        assert "V2 auth unavailable" in exc_info.value.message

    @respx.mock
    def test_login_server_error(self, monkeypatch):
        monkeypatch.setattr(client_mod, "get_username", lambda: "user@test.com")
        monkeypatch.setattr(client_mod, "get_password", lambda: "pass123")
        respx.post(V2_SIGNON_URL).mock(
            return_value=httpx.Response(500, content=b"Server Error")
        )
        with pytest.raises(TickTickAPIError) as exc_info:
            _v2_login()
        assert exc_info.value.status_code == 500

    @respx.mock
    def test_login_2fa_required(self, monkeypatch):
        monkeypatch.setattr(client_mod, "get_username", lambda: "user@test.com")
        monkeypatch.setattr(client_mod, "get_password", lambda: "pass123")
        respx.post(V2_SIGNON_URL).mock(
            return_value=httpx.Response(200, json={"authId": "abc", "verificationCode": True})
        )
        with pytest.raises(TickTickAPIError) as exc_info:
            _v2_login()
        assert "verification code" in exc_info.value.message.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  Live tests (real API — opt-in)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.live
class TestLiveV1:
    """Hit the real TickTick V1 API. Run with: pytest -m live"""

    def test_get_projects(self, require_api_token):
        projects = get_projects()
        assert isinstance(projects, list)
        assert all(isinstance(p, Project) for p in projects)

    def test_get_task_not_found(self, require_api_token):
        with pytest.raises(TickTickAPIError) as exc_info:
            get_task("nonexistent_project", "nonexistent_task")
        assert exc_info.value.status_code in (404, 400)


@pytest.mark.live
class TestLiveV2:
    """Hit the real TickTick V2 API. Run with: pytest -m live"""

    def test_sync_all(self, require_session_token):
        sync = sync_all()
        assert isinstance(sync, SyncResponse)

    def test_get_user_status(self, require_session_token):
        status = get_user_status()
        assert isinstance(status, UserStatus)
        assert status.userId is not None

    def test_get_all_tasks(self, require_session_token):
        tasks = get_all_tasks()
        assert isinstance(tasks, list)

    def test_get_tags(self, require_session_token):
        tags = get_tags()
        assert isinstance(tags, list)
        assert all(isinstance(t, Tag) for t in tags)

    def test_get_habits(self, require_session_token):
        habits = get_habits()
        assert isinstance(habits, list)
