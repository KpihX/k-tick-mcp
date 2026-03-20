"""
TickTick API client — V1 (Official) + V2 (Unofficial) dual-stack.

This module remains the stable public facade used by the MCP server and tests.
Implementation is split into transport and operation modules under
`k_tick_mcp.client_api`.
"""
from __future__ import annotations

from .config import (
    get_api_token,
    get_session_token,
    get_username,
    get_password,
    has_v2_auth,
    refresh_session_from_vault,
)
from .client_api.transport import *
from .client_api.projects import *
from .client_api.tasks import *
from .client_api.habits import *
from .client_api.stats import *
