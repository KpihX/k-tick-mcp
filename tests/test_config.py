"""
Tests for k_tick_mcp.config — 2-tier secrets resolver, bw-env integration.

Markers:
  @unit        — mocked, no I/O.
  @integration — real bw-env / real filesystem.
"""
from __future__ import annotations

import os
import importlib
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import k_tick_mcp.config as config_mod
from k_tick_mcp.config import (
    load_config,
    _bwenv_available,
    _shell_read_env,
    _try_bwenv_restart,
    _write_to_dotenv,
    _resolve_env,
    get_api_token,
    get_session_token,
    refresh_session_from_vault,
    get_username,
    get_password,
    has_v2_auth,
    SecretsUnavailableError,
    SessionTokenExpiredError,
    CONFIG_PATH,
    ENV_API_TOKEN,
    ENV_SESSION_TOKEN,
    ENV_USERNAME,
    ENV_PASSWORD,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Unit tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestLoadConfig:
    """load_config(): YAML parsing from disk (or defaults)."""

    def test_returns_dict(self):
        cfg = load_config(CONFIG_PATH)
        assert isinstance(cfg, dict)

    def test_has_expected_sections(self):
        cfg = load_config(CONFIG_PATH)
        # config.yaml should have at least "secrets" and "api"
        assert "secrets" in cfg or "api" in cfg

    def test_missing_file_returns_empty(self, tmp_path):
        load_config.cache_clear()
        result = load_config(tmp_path / "nonexistent.yaml")
        assert result == {}
        load_config.cache_clear()  # reset for other tests

    def test_invalid_yaml_returns_empty(self, tmp_path):
        load_config.cache_clear()
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(":\n  - :\n  invalid: [unmatched", encoding="utf-8")
        result = load_config(bad_yaml)
        assert result == {}
        load_config.cache_clear()


@pytest.mark.unit
class TestBwenvAvailable:
    """_bwenv_available(): checks if 'bw-env' is on PATH."""

    def test_available_when_which_returns_path(self, mock_bwenv):
        assert _bwenv_available() is True

    def test_unavailable_when_which_returns_none(self, no_bwenv):
        assert _bwenv_available() is False


@pytest.mark.unit
class TestSecretsUnavailableError:
    def test_structure(self):
        e = SecretsUnavailableError(
            ENV_API_TOKEN,
            tried=["Tier 1: os.environ", "Tier 2: skipped"],
            hints=["Check your vault"],
        )
        assert e.key == ENV_API_TOKEN
        assert len(e.tried) == 2
        assert len(e.hints) == 1
        assert ENV_API_TOKEN in str(e)

    def test_is_runtime_error(self):
        e = SecretsUnavailableError("X", tried=[], hints=[])
        assert isinstance(e, RuntimeError)


@pytest.mark.unit
class TestSessionTokenExpiredError:
    def test_structure(self):
        e = SessionTokenExpiredError(tried=["vault refresh", "re-login"])
        assert "expired" in str(e).lower()
        assert isinstance(e, RuntimeError)


@pytest.mark.unit
class TestResolveEnvTier1:
    """_resolve_env(): Tier 1 from os.environ (mocked)."""

    def test_resolves_from_env(self, fake_env):
        val = _resolve_env(ENV_API_TOKEN)
        assert val == fake_env[ENV_API_TOKEN]

    def test_returns_none_when_missing(self, clean_env, no_bwenv):
        val = _resolve_env(ENV_API_TOKEN)
        assert val is None

    def test_required_raises_when_missing(self, clean_env, no_bwenv):
        with pytest.raises(SecretsUnavailableError) as exc_info:
            _resolve_env(ENV_API_TOKEN, required=True)
        assert exc_info.value.key == ENV_API_TOKEN
        assert len(exc_info.value.tried) >= 1

    def test_skip_tier1_ignores_env(self, fake_env, no_bwenv):
        val = _resolve_env(ENV_API_TOKEN, skip_tier1=True)
        assert val is None  # should skip env and bw-env unavailable → None


@pytest.mark.unit
class TestResolveEnvTier2:
    """_resolve_env(): Tier 2 via bw-env (mocked)."""

    def test_tier2a_login_shell_read(self, clean_env, mock_bwenv, monkeypatch):
        """If Tier 1 misses but login shell finds it, should succeed."""
        monkeypatch.setattr(
            config_mod, "_shell_read_env",
            lambda key: "vault_token_abc123" if key == ENV_API_TOKEN else None,
        )
        val = _resolve_env(ENV_API_TOKEN)
        assert val == "vault_token_abc123"
        # Should also be injected into os.environ
        assert os.environ.get(ENV_API_TOKEN) == "vault_token_abc123"

    def test_tier2b_restart_then_read(self, clean_env, mock_bwenv, monkeypatch):
        """If Tier 2a misses but restart succeeds → shell read works."""
        call_count = {"n": 0}

        def _fake_shell_read(key):
            call_count["n"] += 1
            # First call = Tier 2a → None; second call (after restart) → value
            if call_count["n"] >= 2:
                return "fresh_token_after_restart"
            return None

        monkeypatch.setattr(config_mod, "_shell_read_env", _fake_shell_read)
        monkeypatch.setattr(config_mod, "_try_bwenv_restart", lambda: True)

        val = _resolve_env(ENV_API_TOKEN)
        assert val == "fresh_token_after_restart"

    def test_cache_to_dotenv(self, clean_env, mock_bwenv, monkeypatch, backup_dotenv):
        """cache_to_dotenv=True should write the resolved value to .env."""
        monkeypatch.setattr(
            config_mod, "_shell_read_env",
            lambda key: "session_from_vault",
        )
        written = {}
        monkeypatch.setattr(
            config_mod, "_write_to_dotenv",
            lambda k, v: written.update({k: v}),
        )
        val = _resolve_env(ENV_SESSION_TOKEN, cache_to_dotenv=True)
        assert val == "session_from_vault"
        assert written.get(ENV_SESSION_TOKEN) == "session_from_vault"


@pytest.mark.unit
class TestPublicGetters:
    """get_api_token(), get_session_token(), etc."""

    def test_get_api_token_from_env(self, fake_env):
        assert get_api_token() == fake_env[ENV_API_TOKEN]

    def test_get_api_token_raises_when_missing(self, clean_env, no_bwenv):
        with pytest.raises(SecretsUnavailableError):
            get_api_token()

    def test_get_session_token_from_env(self, fake_env):
        assert get_session_token() == fake_env[ENV_SESSION_TOKEN]

    def test_get_session_token_none_when_missing(self, clean_env, no_bwenv):
        # session token is not required → returns None
        assert get_session_token() is None

    def test_get_username(self, fake_env):
        assert get_username() == "test@example.com"

    def test_get_password(self, fake_env):
        assert get_password() == "hunter2"

    def test_has_v2_auth_true_with_session(self, fake_env):
        assert has_v2_auth() is True

    def test_has_v2_auth_false_without_anything(self, clean_env, no_bwenv):
        assert has_v2_auth() is False

    def test_has_v2_auth_true_with_credentials_only(self, clean_env, no_bwenv, monkeypatch):
        monkeypatch.setenv(ENV_USERNAME, "user@example.com")
        monkeypatch.setenv(ENV_PASSWORD, "pw")
        assert has_v2_auth() is True


@pytest.mark.unit
class TestRefreshSessionFromVault:
    """refresh_session_from_vault(): force re-read, skip Tier 1."""

    def test_returns_new_token_when_different(self, fake_env, mock_bwenv, monkeypatch):
        monkeypatch.setattr(
            config_mod, "_shell_read_env",
            lambda key: "brand_new_token",
        )
        monkeypatch.setattr(
            config_mod, "_write_to_dotenv", lambda k, v: None,
        )
        result = refresh_session_from_vault()
        assert result == "brand_new_token"

    def test_returns_none_when_same(self, fake_env, mock_bwenv, monkeypatch):
        # Vault returns same value as current env → no refresh
        monkeypatch.setattr(
            config_mod, "_shell_read_env",
            lambda key: fake_env[ENV_SESSION_TOKEN],
        )
        result = refresh_session_from_vault()
        assert result is None

    def test_returns_none_when_unavailable(self, fake_env, no_bwenv):
        result = refresh_session_from_vault()
        assert result is None


@pytest.mark.unit
class TestWriteToDotenv:
    """_write_to_dotenv(): file write/update logic."""

    def test_creates_file_if_missing(self, tmp_path, monkeypatch):
        dotenv = tmp_path / "pkg" / ".env"
        monkeypatch.setattr(config_mod, "_DOTENV_PATH", dotenv)
        _write_to_dotenv("MY_KEY", "my_value")
        assert dotenv.exists()
        content = dotenv.read_text()
        assert "MY_KEY=my_value" in content

    def test_updates_existing_key(self, tmp_path, monkeypatch):
        dotenv = tmp_path / ".env"
        dotenv.write_text("MY_KEY=old\nOTHER=keep\n")
        monkeypatch.setattr(config_mod, "_DOTENV_PATH", dotenv)
        _write_to_dotenv("MY_KEY", "new_value")
        content = dotenv.read_text()
        assert "MY_KEY=new_value" in content
        assert "OTHER=keep" in content
        assert "MY_KEY=old" not in content

    def test_appends_new_key(self, tmp_path, monkeypatch):
        dotenv = tmp_path / ".env"
        dotenv.write_text("EXISTING=yes\n")
        monkeypatch.setattr(config_mod, "_DOTENV_PATH", dotenv)
        _write_to_dotenv("NEW_KEY", "hello")
        content = dotenv.read_text()
        assert "EXISTING=yes" in content
        assert "NEW_KEY=hello" in content


@pytest.mark.unit
class TestShellReadEnv:
    """_shell_read_env(): subprocess login shell read (mocked)."""

    def test_returns_value(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = "  the_token_value  "
        monkeypatch.setattr(
            config_mod.subprocess, "run", lambda *a, **kw: mock_result,
        )
        assert _shell_read_env("SOME_KEY") == "the_token_value"

    def test_returns_none_on_empty(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = ""
        monkeypatch.setattr(
            config_mod.subprocess, "run", lambda *a, **kw: mock_result,
        )
        assert _shell_read_env("SOME_KEY") is None

    def test_returns_none_on_timeout(self, monkeypatch):
        import subprocess
        monkeypatch.setattr(
            config_mod.subprocess, "run",
            lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("zsh", 5)),
        )
        assert _shell_read_env("SOME_KEY") is None


# ═══════════════════════════════════════════════════════════════════════════════
#  Integration tests (require real bw-env on PATH)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestBwenvIntegration:
    """Tests that talk to the real bw-env binary. Skipped if bw-env absent."""

    def test_bwenv_is_on_path(self, require_bwenv):
        assert _bwenv_available() is True

    def test_shell_read_env_returns_something(self, require_bwenv):
        """
        If bw-env is running and secrets are synced, at least one of the
        managed keys should be readable.
        """
        results = {
            k: _shell_read_env(k)
            for k in (ENV_API_TOKEN, ENV_SESSION_TOKEN)
        }
        # At least one should have a value (if vault is unlocked)
        has_any = any(v for v in results.values())
        if not has_any:
            pytest.skip("bw-env is installed but vault appears locked or empty")
        assert has_any

    def test_get_api_token_real(self, require_bwenv, require_api_token):
        token = get_api_token()
        assert isinstance(token, str)
        assert len(token) > 10

    def test_get_session_token_real(self, require_bwenv, require_session_token):
        token = get_session_token()
        assert isinstance(token, str)
        assert len(token) > 10

    def test_has_v2_auth_real(self, require_bwenv, require_session_token):
        assert has_v2_auth() is True

    def test_refresh_session_from_vault_real(self, require_bwenv, require_session_token):
        """refresh_session_from_vault() should return None (same value) or a new token."""
        result = refresh_session_from_vault()
        # Either None (same as current) or a new string
        assert result is None or isinstance(result, str)
