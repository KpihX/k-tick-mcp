from __future__ import annotations

import anyio

import tick_mcp.http_app as http_app


def test_health_route_exposes_http_transport(monkeypatch) -> None:
    monkeypatch.setattr(http_app.daemon, "read_pid", lambda: 4242)
    monkeypatch.setattr(http_app.daemon, "is_running", lambda pid: pid == 4242)
    monkeypatch.setenv("TICKTICK_API_TOKEN", "api-token")
    monkeypatch.setenv("TICKTICK_SESSION_TOKEN", "session-token")
    monkeypatch.setenv("TICKTICK_USERNAME", "user@example.com")
    monkeypatch.setenv("TICKTICK_PASSWORD", "password")

    response = anyio.run(http_app.health, None)
    payload = response.body
    assert response.status_code == 200
    data = __import__("json").loads(payload)
    assert data["product"] == "tick-mcp"
    assert data["transport"] == "streamable-http"
    assert data["running"] is True
    assert data["pid"] == 4242
    assert data["auth"]["api_token_present"] is True
    assert data["auth"]["session_token_present"] is True
    assert data["auth"]["username_present"] is True
    assert data["auth"]["password_present"] is True
    assert data["auth"]["v2_available"] is True


def test_admin_status_mentions_ssh_and_telegram(monkeypatch) -> None:
    monkeypatch.setattr(http_app.daemon, "read_pid", lambda: None)
    monkeypatch.setattr(http_app, "telegram_admin_enabled", lambda: True)
    monkeypatch.setattr(http_app, "status_summary_text", lambda: "status-ok")
    monkeypatch.setenv("TICKTICK_API_TOKEN", "api-token")
    monkeypatch.setenv("TICKTICK_SESSION_TOKEN", "session-token")

    response = anyio.run(http_app.admin_status, None)
    payload = response.body
    assert response.status_code == 200
    data = __import__("json").loads(payload)
    assert data["product"] == "tick-mcp"
    assert data["admin"]["ssh_admin"]["supported"] is True
    assert data["admin"]["telegram_admin"]["token_env"] == "TELEGRAM_TICK_HOMELAB_TOKEN"
    assert data["admin"]["telegram_admin"]["allowed_chat_ids_env"] == "TELEGRAM_CHAT_IDS"
    assert data["admin"]["telegram_admin"]["enabled"] is True
    assert data["admin"]["auth_probe"]["api_token_present"] is True
    assert data["admin"]["auth_probe"]["session_token_present"] is True
    assert data["admin"]["status_summary"] == "status-ok"
