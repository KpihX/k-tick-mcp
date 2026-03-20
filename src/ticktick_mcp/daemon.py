"""
daemon.py — PID file manager for ticktick-mcp server lifecycle.
Mirrors the daemon management pattern from bw-mcp.
"""
import os
import signal
from pathlib import Path


def _pid_file_path() -> Path:
    from .config import load_config
    config = load_config()
    state_dir = Path(
        config.get("server", {}).get("state_directory", "~/.mcps/ticktick")
    ).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "ticktick-mcp.pid"


def write_pid(pid: int) -> None:
    _pid_file_path().write_text(str(pid))


def read_pid() -> int | None:
    p = _pid_file_path()
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except (ValueError, OSError):
        return None


def clear_pid() -> None:
    try:
        _pid_file_path().unlink(missing_ok=True)
    except OSError:
        pass


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
