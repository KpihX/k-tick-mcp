# Changelog

All notable changes to **k-tick-mcp** will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2025-07-13

### Added

- **46 MCP tools** covering tasks, projects, tags, habits, focus, kanban, folders, subtasks, sync, and user stats.
- **Dual API support** — V1 (official Open API with OAuth2/PAT) and V2 (unofficial web API for extended features).
- **V2 auto-login** — `ticktick-admin session refresh` CLI command for interactive session token renewal.
- **Batch operations** — `batch_create_tasks`, `batch_update_tasks`, `batch_delete_tasks`, `move_tasks`.
- **Kanban management** — `list_columns`, `manage_columns` for board-based workflows.
- **Habit tracking** — full CRUD, check-in, records retrieval, and section listing.
- **Focus / Pomodoro** — `get_focus_stats` for daily focus time analytics.
- **History retrieval** — `get_completed_tasks`, `get_deleted_tasks` with date-range filtering.
- **Helper tools** — `build_recurrence_rule` (RRULE builder), `build_reminder` (trigger builder), `ticktick_guide` (contextual usage guide), `check_v2_availability`.
- **Pydantic v2 models** — `Task`, `Project`, `Habit`, `Tag`, `ChecklistItem`, `SyncResponse`, and more with field validation and coercion.
- **Externalized configuration** — `config.yaml` for API endpoints, timeouts, user-agent, and login paths.
- **`.env` support** — environment variables loaded from `.env` file via `python-dotenv`; `.env.example` with comprehensive auth documentation.
- **Two CLI entry points** — `ticktick-mcp` (MCP stdio server) and `ticktick-admin` (admin/diagnostic CLI via Typer).
- **Test suite** — 135 unit tests (mocked, no network) + 12 live integration scripts (508 assertions against real API).
