"""
Focus, user, and productivity statistics operations.
"""
from __future__ import annotations

from ..models import UserStatus
from .transport import _v2_get

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

__all__ = [
    'get_focus_heatmap', 'get_focus_distribution', 'get_user_status',
    'get_user_profile', 'get_user_preferences', 'get_productivity_stats',
]
