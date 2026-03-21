# TODO

- [ ] Add a dedicated operator runbook for expired TickTick session recovery, including Telegram failure modes and SSH fallback.
- [ ] Add authenticated read-only admin HTTP endpoints for config and MCP catalog inspection if Telegram read surfaces become too narrow.
- [ ] Add automated end-to-end smoke coverage for Telegram admin command dispatch against a disposable test harness.
- [ ] Review whether `tests/live/` should be wrapped by one reproducible operator script for local verification against a real TickTick account.
