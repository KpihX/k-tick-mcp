# k-tick-mcp

[![PyPI](https://img.shields.io/pypi/v/k-tick-mcp)](https://pypi.org/project/k-tick-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/k-tick-mcp)](https://pypi.org/project/k-tick-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MCP server for TickTick** — manage tasks, projects, habits, tags, focus stats, and more through the [Model Context Protocol](https://modelcontextprotocol.io/).

**71 tools** exposed over MCP, covering both the official TickTick Open API (V1) and the unofficial web API (V2) for features not yet available publicly.

---

## Features

| Category | Tools |
|---|---|
| **Tasks** | `create_task` · `update_task` · `complete_task` · `reopen_task` · `delete_task` · `get_task_detail` · `get_project_tasks` · `get_inbox` · `get_all_tasks` |
| **Batch** | `batch_create_tasks` · `batch_update_tasks` · `batch_delete_tasks` · `move_tasks` |
| **Projects** | `create_project` · `update_project` · `delete_project` · `get_project_detail` · `list_projects` |
| **Query / Search** | `workspace_map` · `query_projects` · `query_folders` · `query_tasks` · `query_notes` · `query_agenda` · `query_task_history` · `list_query_presets` · `save_query_preset` · `run_query_preset` · `delete_query_preset` |
| **Views** | `tasks_of_today` · `events_of_today` · `week_agenda` · `week_overview` · `upcoming_tasks` · `overdue_tasks` · `stale_tasks` · `priority_dashboard` |
| **Verified Actions** | `create_subtask` · `verified_create_project` · `verified_set_subtask_parent` · `verified_move_tasks` · `verified_batch_move` · `verified_assign_project_folder` |
| **Tags** | `create_tag` · `update_tag` · `rename_tag` · `merge_tags` · `delete_tag` · `list_tags` |
| **Habits** | `create_habit` · `update_habit` · `delete_habit` · `list_habits` · `habit_checkin` · `get_habit_records` · `list_habit_sections` |
| **Kanban** | `list_columns` · `manage_columns` |
| **Folders** | `list_project_folders` · `manage_project_folders` |
| **Focus** | `get_focus_stats` |
| **History** | `get_completed_tasks` · `get_deleted_tasks` |
| **Subtasks** | `set_subtask_parent` |
| **Sync / Stats** | `full_sync` · `get_user_status` · `get_productivity_stats` |
| **Utilities** | `ticktick_guide` · `check_v2_availability` · `build_recurrence_rule` · `build_reminder` |

### Query / Search highlights

- **Structured task filtering** — folders, projects, tags, parent/subtask shape, reminders, recurrence, checklist presence, and priorities.
- **Time-aware agenda access** — query by date range, datetime range, and HH:MM time windows without forcing a full sync first.
- **Grep-like matching** — substring search, `any` / `all` / `phrase` keyword modes, regex, and exclusion regex across chosen fields.
- **Targeted note search** — notes are fetched only from NOTE projects in scope instead of materializing the whole workspace.
- **Workspace navigation** — folder/project map with optional active task counts to inspect the account structure before acting.
- **Ready-made operational views** — day view, week window, upcoming due tasks, overdue/stale detection, and priority summaries built on the same filter engine.
- **Saved query presets** — persist reusable task/note/agenda/history/week-overview queries and execute them later without rebuilding the filter set.

### Verified workflow helpers

- **Subtask-safe creation** — `create_subtask` creates the child, links it, then verifies `parentId` and `childIds`.
- **Move verification** — `verified_move_tasks` re-reads destination projects and confirms every moved task is actually there.
- **Folder assignment verification** — `verified_assign_project_folder` verifies the persisted `groupId` through V2 sync, not through the misleading V1 response.

## Package Layout

```text
src/k_tick_mcp/
├── mcp_api/
│   ├── core.py          # shared FastMCP instance, catalog, helpers
│   ├── utilities.py     # discovery + helper tools
│   ├── projects.py      # project CRUD tools
│   ├── tasks_read.py    # inbox / project / task reads
│   ├── tasks_write.py   # task mutation tools
│   ├── tasks_batch.py   # batch + structural task operations
│   ├── read.py          # high-level query/search, views, and saved presets
│   ├── verified.py      # safe wrappers with read-back verification + rollback hints
│   ├── folders.py       # folders + kanban columns
│   ├── tags.py          # tag tools
│   ├── habits.py        # habit tools
│   ├── history.py       # completed / deleted history
│   └── stats.py         # focus and user/productivity stats
├── services/
│   └── query.py         # reusable filtering, range and grep-like planning
├── client_api/
│   ├── transport.py     # auth, sessions, low-level V1/V2 HTTP helpers
│   ├── projects.py      # projects, folders, columns, tags
│   ├── tasks.py         # tasks, sync, batch, history
│   ├── habits.py        # habits and check-ins
│   └── stats.py         # focus and user/productivity stats
├── client.py            # stable public facade over client_api/*
├── models.py            # pydantic contracts
├── server.py            # stable public import surface for the MCP server
└── main.py              # CLI entrypoint
```

## Installation

```bash
# recommended — installs as a standalone tool
uv tool install k-tick-mcp

# or via pip
pip install k-tick-mcp
```

This provides two commands:

| Command | Description |
|---|---|
| `ticktick-mcp` | Start the MCP server (stdio transport) |
| `ticktick-admin` | CLI helper — session refresh, diagnostics |

## Configuration

### 1. Environment variables

Copy the example file and fill in your tokens:

```bash
cp src/k_tick_mcp/.env.example src/k_tick_mcp/.env
```

| Variable | Required | Description |
|---|---|---|
| `TICKTICK_API_TOKEN` | **Yes** | V1 Open API bearer token (PAT or OAuth2) |
| `TICKTICK_SESSION_TOKEN` | No | V2 session cookie for extended features |

**Getting a V1 token (simplest):**

1. Open TickTick → Settings → Integrations → API
2. Copy the displayed Personal Access Token

**Getting a V2 session token:**

1. Log in to [ticktick.com](https://ticktick.com) in your browser
2. DevTools → Application → Cookies → copy the `t` cookie value

Or use the CLI to auto-login:

```bash
ticktick-admin session refresh
```

### 2. Server config

Runtime settings live in `src/k_tick_mcp/config.yaml` — API endpoints, timeouts, and user-agent are all externalised there.

## MCP Client Integration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "ticktick-mcp",
      "env": {
        "TICKTICK_API_TOKEN": "your-v1-token",
        "TICKTICK_SESSION_TOKEN": "your-v2-token"
      }
    }
  }
}
```

### VS Code (GitHub Copilot)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "ticktick": {
      "command": "ticktick-mcp",
      "env": {
        "TICKTICK_API_TOKEN": "your-v1-token",
        "TICKTICK_SESSION_TOKEN": "your-v2-token"
      }
    }
  }
}
```

### Other MCP clients

Any client that supports the stdio transport can launch `ticktick-mcp` as a subprocess.

## Development

```bash
# Clone & install dev deps
git clone https://github.com/kpihx/k-tick-mcp.git
cd k-tick-mcp
uv sync --group dev

# Unit tests (153 selected unit tests, no network)
uv run pytest

# Live tests against real TickTick API (requires tokens in .env)
uv run pytest -m live
```

### Test suite

- **153 selected unit tests** — pure logic, mocked HTTP, zero network
- **12 live integration scripts** — 508 assertions against the real TickTick API

## License

[MIT](LICENSE) © 2025 Ivann KAMDEM
