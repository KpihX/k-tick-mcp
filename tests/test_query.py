"""
Unit tests for the high-level TickTick query layer.
"""
from __future__ import annotations

import pytest

from k_tick_mcp.models import Project, ProjectData, ProjectGroup, Task, ChecklistItem
from k_tick_mcp.query import TaskFilterSpec, TickTickQueryService


class FakeClient:
    def __init__(self) -> None:
        self.calls = {
            "get_projects": 0,
            "get_project_groups": 0,
            "get_all_tasks": 0,
            "get_project_data": 0,
            "get_completed_tasks": 0,
            "get_deleted_tasks": 0,
        }

        self.projects = [
            Project(id="p1", name="Alpha", kind="TASK", groupId="g1"),
            Project(id="p2", name="Beta", kind="TASK"),
            Project(id="p3", name="Research Notes", kind="NOTE", groupId="g2"),
        ]
        self.folders = [
            ProjectGroup(id="g1", name="Work"),
            ProjectGroup(id="g2", name="Notes"),
        ]
        self.tasks = [
            Task(
                id="t1",
                projectId="p1",
                title="Prepare quarterly report",
                content="Budget and report review",
                dueDate="2026-03-21T09:30:00+0000",
                priority=5,
                tags=["work", "report"],
                reminders=["TRIGGER:-PT30M"],
            ),
            Task(
                id="t2",
                projectId="p1",
                title="Team lunch",
                dueDate="2026-03-21T12:30:00+0000",
                priority=1,
            ),
            Task(
                id="t3",
                projectId="p2",
                title="Refactor ticktick query layer",
                content="Need regex-friendly filters for projects and notes.",
                startDate="2026-03-22T14:00:00+0000",
                priority=3,
                tags=["dev", "api"],
                items=[ChecklistItem(title="ship service", status=0)],
            ),
            Task(
                id="t4",
                projectId="p1",
                title="Report appendix",
                dueDate="2026-03-21T10:15:00+0000",
                priority=3,
                parentId="t1",
            ),
        ]
        self.project_items = {
            "p1": ProjectData(
                project=Project(id="p1", name="Alpha", kind="TASK", groupId="g1"),
                tasks=[self.tasks[0], self.tasks[1], self.tasks[3]],
            ),
            "p2": ProjectData(
                project=Project(id="p2", name="Beta", kind="TASK"),
                tasks=[self.tasks[2]],
            ),
            "p3": ProjectData(
                project=Project(id="p3", name="Research Notes", kind="NOTE", groupId="g2"),
                tasks=[
                    Task(
                        id="n1",
                        projectId="p3",
                        kind="NOTE",
                        title="TickTick architecture notes",
                        content="Need a grep-like search layer for tasks and notes.",
                        modifiedTime="2026-03-20T09:00:00+0000",
                    ),
                    Task(
                        id="n2",
                        projectId="p3",
                        kind="NOTE",
                        title="Travel ideas",
                        content="Berlin and Paris options",
                        modifiedTime="2026-03-18T09:00:00+0000",
                    ),
                ],
            )
        }
        self.completed = [
            Task(
                id="c1",
                projectId="p1",
                title="Finished report",
                completedTime="2026-03-19T18:00:00+0000",
                dueDate="2026-03-19T17:00:00+0000",
                status=2,
                tags=["report"],
            )
        ]

    def get_projects(self):
        self.calls["get_projects"] += 1
        return self.projects

    def get_project_groups(self):
        self.calls["get_project_groups"] += 1
        return self.folders

    def get_all_tasks(self):
        self.calls["get_all_tasks"] += 1
        return self.tasks

    def get_project_data(self, project_id: str):
        self.calls["get_project_data"] += 1
        return self.project_items[project_id]

    def get_completed_tasks(self, from_date: str, to_date: str, status: str, limit: int):
        self.calls["get_completed_tasks"] += 1
        return self.completed

    def get_deleted_tasks(self, start: int = 0, limit: int = 500):
        self.calls["get_deleted_tasks"] += 1
        return []


@pytest.mark.unit
class TestQueryService:
    def test_query_tasks_supports_ranges_tags_and_subtask_filters(self):
        service = TickTickQueryService(FakeClient())
        spec = TaskFilterSpec(
            folder_names=["Work"],
            tags=["report"],
            tag_mode="all",
            due_from="2026-03-21",
            due_to="2026-03-21",
            time_from="09:00",
            time_to="10:00",
            parent_only=True,
            limit=10,
        )

        result = service.query_tasks(spec)

        assert result["plan"]["source"] == "project_data"
        assert [item["id"] for item in result["items"]] == ["t1"]

    def test_query_tasks_supports_regex_and_field_selection(self):
        service = TickTickQueryService(FakeClient())
        spec = TaskFilterSpec(
            regex=r"regex-friendly filters",
            search_fields=["content"],
            limit=10,
        )

        result = service.query_tasks(spec)

        assert [item["id"] for item in result["items"]] == ["t3"]

    def test_query_notes_fetches_only_note_projects_in_scope(self):
        fake = FakeClient()
        service = TickTickQueryService(fake)
        spec = TaskFilterSpec(
            folder_names=["Notes"],
            text_query="grep-like search",
            keyword_mode="phrase",
            limit=10,
        )

        result = service.query_notes(spec)

        assert [item["id"] for item in result["items"]] == ["n1"]
        assert fake.calls["get_project_data"] == 1
        assert fake.calls["get_all_tasks"] == 0

    def test_query_agenda_filters_time_windows(self):
        service = TickTickQueryService(FakeClient())
        spec = TaskFilterSpec(
            timed_only=True,
            time_from="10:00",
            time_to="13:00",
            limit=10,
        )

        result = service.query_agenda(
            from_dt="2026-03-21T00:00:00+0000",
            to_dt="2026-03-21T23:59:59+0000",
            spec=spec,
        )

        assert [item["id"] for item in result["items"]] == ["t4", "t2"]

    def test_workspace_map_with_counts(self):
        service = TickTickQueryService(FakeClient())

        result = service.workspace_map(include_counts=True)

        work_folder = next(folder for folder in result["folders"] if folder["id"] == "g1")
        alpha_project = next(project for project in work_folder["projects"] if project["id"] == "p1")
        assert alpha_project["task_count_active"] == 3

    def test_query_task_history_uses_completed_endpoint(self):
        service = TickTickQueryService(FakeClient())
        spec = TaskFilterSpec(tags=["report"], limit=10)

        result = service.query_task_history(
            history_source="completed",
            from_date="2026-03-01 00:00:00",
            to_date="2026-03-31 23:59:59",
            spec=spec,
        )

        assert result["plan"]["source"] == "history:completed"
        assert [item["id"] for item in result["items"]] == ["c1"]
