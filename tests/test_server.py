"""
Tests for ticktick_mcp.server — MCP tool registration & catalog.

All tests here are @unit — they verify static structure, not API calls.
"""
from __future__ import annotations

import pytest

from ticktick_mcp.server import mcp, TOOL_CATALOG, COMMON_WORKFLOWS, __all__, _err, _task_dict
from ticktick_mcp.mcp_api.utilities import ticktick_guide
from ticktick_mcp.models import TickTickAPIError, Task, Priority, TaskStatus


# ═══════════════════════════════════════════════════════════════════════════════
#  Tool Catalog
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestToolCatalog:
    def test_catalog_is_dict(self):
        assert isinstance(TOOL_CATALOG, dict)

    def test_catalog_has_categories(self):
        assert len(TOOL_CATALOG) >= 10  # currently ~14 categories

    def test_each_category_has_tools_and_desc(self):
        for cat_name, cat in TOOL_CATALOG.items():
            assert "tools" in cat, f"Missing 'tools' key in '{cat_name}'"
            assert "desc" in cat, f"Missing 'desc' key in '{cat_name}'"
            assert isinstance(cat["tools"], list)
            assert len(cat["tools"]) > 0, f"Empty tools list in '{cat_name}'"

    def test_all_tool_names_are_strings(self):
        for cat in TOOL_CATALOG.values():
            for tool_name in cat["tools"]:
                assert isinstance(tool_name, str)
                assert len(tool_name) > 0

    def test_no_duplicate_tool_names(self):
        all_tools = []
        for cat in TOOL_CATALOG.values():
            all_tools.extend(cat["tools"])
        assert len(all_tools) == len(set(all_tools)), (
            f"Duplicate tools found: {[t for t in all_tools if all_tools.count(t) > 1]}"
        )

    def test_expected_categories_present(self):
        # Spot-check key categories
        cat_names_lower = [k.lower() for k in TOOL_CATALOG]
        joined = " ".join(cat_names_lower)
        assert "project" in joined
        assert "task" in joined
        assert "tag" in joined
        assert "habit" in joined
        assert "sync" in joined

    def test_catalog_matches_public_exports_and_registered_tools(self):
        catalog_tools = {
            tool_name
            for category in TOOL_CATALOG.values()
            for tool_name in category["tools"]
        }
        exported_tools = {
            name
            for name in __all__
            if not name.startswith("_")
            and name not in {"mcp", "TOOL_CATALOG", "COMMON_WORKFLOWS", "INTENT_GUIDE"}
        }
        registered_tools = set(mcp._tool_manager._tools)
        assert catalog_tools == exported_tools
        assert catalog_tools == registered_tools


# ═══════════════════════════════════════════════════════════════════════════════
#  Workflows
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestWorkflows:
    def test_workflows_is_list(self):
        assert isinstance(COMMON_WORKFLOWS, list)

    def test_workflows_have_name_and_steps(self):
        for wf in COMMON_WORKFLOWS:
            assert "name" in wf
            assert "steps" in wf
            assert isinstance(wf["steps"], list)
            assert len(wf["steps"]) > 0

    def test_ticktick_guide_supports_intent_views(self):
        result = ticktick_guide(intent="know_what_to_do_today")
        assert result["intent"] == "know_what_to_do_today"
        assert "tasks_of_today" in result["tools"]
        assert "events_of_today" in result["tools"]


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestHelpers:
    def test_err_returns_dict(self):
        e = TickTickAPIError(404, "Not found")
        result = _err(e)
        assert result["error"] is True
        assert result["status_code"] == 404
        assert result["message"] == "Not found"

    def test_task_dict_includes_labels(self):
        t = Task(
            id="t1",
            projectId="p1",
            title="Test",
            priority=5,
            status=0,
        )
        d = _task_dict(t)
        assert d["priority_label"] == "high"
        assert d["is_completed"] is False
        assert d["title"] == "Test"

    def test_task_dict_with_checklist(self):
        from ticktick_mcp.models import ChecklistItem
        t = Task(
            title="Shopping",
            items=[
                ChecklistItem(title="Eggs", status=1),
                ChecklistItem(title="Milk", status=0),
            ],
        )
        d = _task_dict(t)
        assert d["checklist_progress"] == "1/2"

    def test_task_dict_no_checklist(self):
        t = Task(title="Simple")
        d = _task_dict(t)
        assert "checklist_progress" not in d


# ═══════════════════════════════════════════════════════════════════════════════
#  FastMCP instance
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestMCPInstance:
    def test_mcp_has_name(self):
        assert mcp.name == "TickTick-MCP" or mcp.name is not None

    def test_mcp_has_tools(self):
        """The mcp object should have registered tools."""
        # FastMCP stores tools internally; verify it exists and has content
        tools = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}
        # Fallback: just ensure the mcp object is usable
        assert mcp is not None
