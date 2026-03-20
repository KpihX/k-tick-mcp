"""
Query and search services for TickTick MCP.

This module provides a higher-level read layer on top of the raw V1/V2 client:
  - targeted workspace navigation (folders / projects / notes)
  - structured task filters (dates, time windows, tags, reminders, hierarchy)
  - grep-like text / regex matching across chosen fields
  - source planning to avoid fetching more state than necessary
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
import re
from typing import Any, Iterable, Optional

from ..models import Priority, Project, ProjectGroup, ProjectKind, Task, TaskStatus


DEFAULT_TASK_FIELDS = ["title", "content", "desc", "tags", "project", "folder"]
DEFAULT_NOTE_FIELDS = ["title", "content", "desc", "project", "folder"]
DEFAULT_PROJECT_FIELDS = ["name", "folder"]
DEFAULT_FOLDER_FIELDS = ["name"]
VALID_TASK_SORT_FIELDS = {
    "title", "dueDate", "startDate", "modifiedTime", "createdTime", "priority", "project", "folder",
}


@dataclass(slots=True)
class QueryPlan:
    """Small execution plan to explain which backing calls are needed."""

    source: str
    project_ids: list[str]
    project_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "project_ids": self.project_ids,
            "project_count": self.project_count,
        }


@dataclass(slots=True)
class TaskFilterSpec:
    """Reusable task filter specification shared by task/note/history queries."""

    project_ids: Optional[list[str]] = None
    project_names: Optional[list[str]] = None
    folder_ids: Optional[list[str]] = None
    folder_names: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    tag_mode: str = "any"
    text_query: Optional[str] = None
    keyword_mode: str = "any"
    regex: Optional[str] = None
    exclude_regex: Optional[str] = None
    search_fields: Optional[list[str]] = None
    due_from: Optional[str] = None
    due_to: Optional[str] = None
    start_from: Optional[str] = None
    start_to: Optional[str] = None
    modified_from: Optional[str] = None
    modified_to: Optional[str] = None
    created_from: Optional[str] = None
    created_to: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    timed_only: bool = False
    all_day: Optional[bool] = None
    min_priority: Optional[int] = None
    priorities: Optional[list[int]] = None
    has_reminders: Optional[bool] = None
    is_recurring: Optional[bool] = None
    has_checklist: Optional[bool] = None
    parent_only: bool = False
    subtasks_only: bool = False
    limit: int = 50
    sort_by: str = "dueDate"
    descending: bool = False


class TickTickQueryService:
    """High-level read/query layer over the TickTick client."""

    def __init__(self, api_client: Any):
        self._client = api_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def workspace_map(
        self,
        include_closed: bool = False,
        include_counts: bool = False,
        project_name_query: Optional[str] = None,
        project_regex: Optional[str] = None,
        folder_name_query: Optional[str] = None,
        folder_regex: Optional[str] = None,
    ) -> dict[str, Any]:
        projects = self._load_projects()
        folders = self._load_folders()
        project_meta = self._project_metadata(projects, folders)

        if not include_closed:
            projects = [project for project in projects if not project.closed]

        if folder_name_query or folder_regex:
            folder_ids = {
                folder.id
                for folder in folders
                if folder.id and self._match_search(
                    self._folder_blob(folder),
                    folder_name_query,
                    "any",
                    folder_regex,
                    None,
                    DEFAULT_FOLDER_FIELDS,
                )
            }
            projects = [project for project in projects if project.groupId in folder_ids]

        if project_name_query or project_regex:
            projects = [
                project
                for project in projects
                if self._match_search(
                    self._project_blob(project, project_meta.get(project.id or "", {})),
                    project_name_query,
                    "any",
                    project_regex,
                    None,
                    DEFAULT_PROJECT_FIELDS,
                )
            ]

        active_counts: dict[str, int] = {}
        if include_counts:
            for task in self._client.get_all_tasks():
                if task.projectId:
                    active_counts[task.projectId] = active_counts.get(task.projectId, 0) + 1

        folder_to_projects: dict[str | None, list[dict[str, Any]]] = {}
        for project in projects:
            meta = project_meta.get(project.id, {})
            row = project.model_dump(exclude_none=False)
            row["folder_name"] = meta.get("folder_name")
            row["task_count_active"] = active_counts.get(project.id, 0) if include_counts else None
            folder_to_projects.setdefault(project.groupId, []).append(row)

        folder_rows = []
        for folder in folders:
            if folder.id not in folder_to_projects:
                continue
            folder_rows.append(
                {
                    **folder.model_dump(exclude_none=False),
                    "project_count": len(folder_to_projects.get(folder.id, [])),
                    "projects": sorted(folder_to_projects.get(folder.id, []), key=lambda item: item.get("name") or ""),
                }
            )

        ungrouped_projects = sorted(folder_to_projects.get(None, []), key=lambda item: item.get("name") or "")
        return {
            "folders": sorted(folder_rows, key=lambda item: item.get("name") or ""),
            "ungrouped_projects": ungrouped_projects,
            "project_count": len(projects),
            "folder_count": len(folder_rows),
            "include_counts": include_counts,
        }

    def query_projects(
        self,
        name_query: Optional[str] = None,
        regex: Optional[str] = None,
        folder_ids: Optional[list[str]] = None,
        folder_names: Optional[list[str]] = None,
        kinds: Optional[list[str]] = None,
        include_closed: bool = False,
        limit: int = 50,
        sort_by: str = "name",
        descending: bool = False,
    ) -> dict[str, Any]:
        projects = self._load_projects()
        folders = self._load_folders()
        project_meta = self._project_metadata(projects, folders)
        allowed_folder_ids = self._resolve_folder_ids(folders, folder_ids, folder_names)
        allowed_kinds = {kind.upper() for kind in (kinds or [])}

        rows: list[dict[str, Any]] = []
        for project in projects:
            if not include_closed and project.closed:
                continue
            if allowed_folder_ids is not None and project.groupId not in allowed_folder_ids:
                continue
            if allowed_kinds and (project.kind or "").upper() not in allowed_kinds:
                continue
            meta = project_meta.get(project.id, {})
            blob = self._project_blob(project, meta)
            if not self._match_search(blob, name_query, "any", regex, None, DEFAULT_PROJECT_FIELDS):
                continue
            row = project.model_dump(exclude_none=False)
            row["folder_name"] = meta.get("folder_name")
            rows.append(row)

        rows.sort(key=lambda item: self._project_sort_key(item, sort_by), reverse=descending)
        return {
            "count": len(rows[:limit]),
            "items": rows[:limit],
            "applied_filters": {
                "folder_ids": folder_ids,
                "folder_names": folder_names,
                "kinds": kinds,
                "include_closed": include_closed,
                "name_query": name_query,
                "regex": regex,
            },
        }

    def query_folders(
        self,
        name_query: Optional[str] = None,
        regex: Optional[str] = None,
        include_project_counts: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        folders = self._load_folders()
        projects = self._load_projects()
        project_counts: dict[str, int] = {}
        if include_project_counts:
            for project in projects:
                if project.groupId:
                    project_counts[project.groupId] = project_counts.get(project.groupId, 0) + 1

        rows: list[dict[str, Any]] = []
        for folder in folders:
            blob = self._folder_blob(folder)
            if not self._match_search(blob, name_query, "any", regex, None, DEFAULT_FOLDER_FIELDS):
                continue
            row = folder.model_dump(exclude_none=False)
            if include_project_counts:
                row["project_count"] = project_counts.get(folder.id or "", 0)
            rows.append(row)

        rows.sort(key=lambda item: item.get("name") or "")
        return {"count": len(rows[:limit]), "items": rows[:limit]}

    def query_tasks(self, spec: TaskFilterSpec) -> dict[str, Any]:
        projects = self._load_projects()
        folders = self._load_folders()
        metadata = self._project_metadata(projects, folders)
        allowed_folder_ids = self._resolve_folder_ids(folders, spec.folder_ids, spec.folder_names)
        selected_project_ids = self._resolve_project_ids(
            projects,
            spec.project_ids,
            spec.project_names,
            allowed_folder_ids,
            kinds=[ProjectKind.TASK.value],
            include_closed=False,
            select_all_if_unscoped=False,
        )
        tasks, plan = self._load_active_tasks(selected_project_ids)
        return self._filter_task_collection(tasks, metadata, spec, plan)

    def query_notes(self, spec: TaskFilterSpec) -> dict[str, Any]:
        projects = self._load_projects()
        folders = self._load_folders()
        metadata = self._project_metadata(projects, folders)
        allowed_folder_ids = self._resolve_folder_ids(folders, spec.folder_ids, spec.folder_names)
        selected_project_ids = self._resolve_project_ids(
            projects,
            spec.project_ids,
            spec.project_names,
            allowed_folder_ids,
            kinds=[ProjectKind.NOTE.value],
            include_closed=False,
            select_all_if_unscoped=True,
        )
        tasks, plan = self._load_project_scoped_items(selected_project_ids, fallback_kind=ProjectKind.NOTE.value)
        return self._filter_task_collection(tasks, metadata, spec, plan, default_fields=DEFAULT_NOTE_FIELDS)

    def query_agenda(
        self,
        from_dt: str,
        to_dt: str,
        spec: TaskFilterSpec,
        date_field: str = "scheduled",
    ) -> dict[str, Any]:
        agenda_spec = TaskFilterSpec(**asdict(spec))
        if date_field == "due":
            agenda_spec.due_from = from_dt
            agenda_spec.due_to = to_dt
            results = self.query_tasks(agenda_spec)
        elif date_field == "start":
            agenda_spec.start_from = from_dt
            agenda_spec.start_to = to_dt
            results = self.query_tasks(agenda_spec)
        else:
            results = self.query_tasks(agenda_spec)

        items = [
            item
            for item in results["items"]
            if self._row_matches_agenda_window(item, from_dt, to_dt, date_field)
        ]
        results["items"] = items[: agenda_spec.limit]
        results["count"] = len(results["items"])
        results["agenda_window"] = {"from": from_dt, "to": to_dt, "date_field": date_field}
        return results

    def query_task_history(
        self,
        history_source: str,
        from_date: Optional[str],
        to_date: Optional[str],
        spec: TaskFilterSpec,
    ) -> dict[str, Any]:
        projects = self._load_projects()
        folders = self._load_folders()
        metadata = self._project_metadata(projects, folders)

        source = history_source.lower()
        if source == "deleted":
            tasks = self._client.get_deleted_tasks(limit=max(spec.limit * 4, 100))
            plan = QueryPlan(source="deleted_tasks", project_ids=[], project_count=0)
        else:
            if not from_date or not to_date:
                raise ValueError("from_date and to_date are required for completed/abandoned history queries.")
            status_name = "Abandoned" if source == "abandoned" else "Completed"
            tasks = self._client.get_completed_tasks(from_date=from_date, to_date=to_date, status=status_name, limit=max(spec.limit * 4, 100))
            plan = QueryPlan(source=f"history:{status_name.lower()}", project_ids=[], project_count=0)

        return self._filter_task_collection(tasks, metadata, spec, plan)

    # ------------------------------------------------------------------
    # Loaders and planning
    # ------------------------------------------------------------------
    def _load_projects(self) -> list[Project]:
        return self._client.get_projects()

    def _load_folders(self) -> list[ProjectGroup]:
        try:
            return self._client.get_project_groups()
        except Exception:
            return []

    def _project_metadata(self, projects: Iterable[Project], folders: Iterable[ProjectGroup]) -> dict[str, dict[str, Any]]:
        folder_by_id = {folder.id: folder for folder in folders if folder.id}
        metadata: dict[str, dict[str, Any]] = {}
        for project in projects:
            folder = folder_by_id.get(project.groupId or "")
            metadata[project.id] = {
                "project_name": project.name,
                "project_kind": project.kind,
                "folder_id": project.groupId,
                "folder_name": folder.name if folder else None,
            }
        return metadata

    def _resolve_folder_ids(
        self,
        folders: list[ProjectGroup],
        folder_ids: Optional[list[str]],
        folder_names: Optional[list[str]],
    ) -> Optional[set[str | None]]:
        selected_ids: set[str | None] = set()
        if folder_ids:
            selected_ids.update(folder_ids)
        if folder_names:
            wanted = {name.lower() for name in folder_names}
            selected_ids.update(folder.id for folder in folders if folder.id and (folder.name or "").lower() in wanted)
        if not selected_ids and not folder_ids and not folder_names:
            return None
        return selected_ids

    def _resolve_project_ids(
        self,
        projects: list[Project],
        project_ids: Optional[list[str]],
        project_names: Optional[list[str]],
        allowed_folder_ids: Optional[set[str | None]],
        kinds: Optional[list[str]],
        include_closed: bool,
        select_all_if_unscoped: bool,
    ) -> list[str]:
        allowed_names = {name.lower() for name in (project_names or [])}
        allowed_kinds = {kind.upper() for kind in (kinds or [])}
        scope_requested = bool(project_ids or allowed_names or allowed_folder_ids)
        selected: list[str] = []

        for project in projects:
            if not include_closed and project.closed:
                continue
            if allowed_kinds and (project.kind or "").upper() not in allowed_kinds:
                continue
            if not scope_requested and not select_all_if_unscoped:
                continue
            if allowed_folder_ids is not None and project.groupId not in allowed_folder_ids:
                continue
            if project_ids and project.id not in project_ids:
                continue
            if allowed_names and (project.name or "").lower() not in allowed_names:
                continue
            selected.append(project.id)

        if project_ids and not selected:
            selected.extend([project_id for project_id in project_ids if project_id])
        return selected

    def _load_active_tasks(self, selected_project_ids: list[str]) -> tuple[list[Task], QueryPlan]:
        if selected_project_ids:
            tasks, plan = self._load_project_scoped_items(selected_project_ids, fallback_kind=ProjectKind.TASK.value)
            return [task for task in tasks if (task.kind or "TEXT") != ProjectKind.NOTE.value], plan

        tasks = self._client.get_all_tasks()
        return tasks, QueryPlan(source="all_active_tasks", project_ids=[], project_count=0)

    def _load_project_scoped_items(self, project_ids: list[str], fallback_kind: str) -> tuple[list[Task], QueryPlan]:
        items: list[Task] = []
        for project_id in project_ids:
            data = self._client.get_project_data(project_id)
            for task in data.tasks:
                if not task.projectId:
                    task.projectId = project_id
                if not task.kind:
                    task.kind = "NOTE" if fallback_kind == ProjectKind.NOTE.value else "TEXT"
                items.append(task)
        plan = QueryPlan(source="project_data", project_ids=project_ids, project_count=len(project_ids))
        return items, plan

    # ------------------------------------------------------------------
    # Task filtering
    # ------------------------------------------------------------------
    def _filter_task_collection(
        self,
        tasks: list[Task],
        project_metadata: dict[str, dict[str, Any]],
        spec: TaskFilterSpec,
        plan: QueryPlan,
        default_fields: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        compiled_regex = re.compile(spec.regex, re.IGNORECASE) if spec.regex else None
        exclude_regex = re.compile(spec.exclude_regex, re.IGNORECASE) if spec.exclude_regex else None
        fields = spec.search_fields or default_fields or DEFAULT_TASK_FIELDS
        rows: list[dict[str, Any]] = []

        for task in tasks:
            meta = project_metadata.get(task.projectId or "", {})
            if not self._match_task_filters(task, meta, spec, fields, compiled_regex, exclude_regex):
                continue
            row = task.model_dump(exclude_none=False)
            row["priority_label"] = Priority.label(task.priority)
            row["is_completed"] = task.is_completed()
            row["allDay"] = task.effective_all_day()
            row["effective_repeat"] = task.effective_repeat()
            row["project_name"] = meta.get("project_name")
            row["folder_id"] = meta.get("folder_id")
            row["folder_name"] = meta.get("folder_name")
            if task.items:
                done = sum(1 for item in task.items if item.is_completed())
                row["checklist_progress"] = f"{done}/{len(task.items)}"
            rows.append(row)

        rows.sort(key=lambda item: self._task_sort_key(item, spec.sort_by), reverse=spec.descending)
        limited = rows[: max(spec.limit, 0)]
        return {
            "count": len(limited),
            "items": limited,
            "plan": plan.to_dict(),
            "applied_filters": {
                "project_ids": spec.project_ids,
                "project_names": spec.project_names,
                "folder_ids": spec.folder_ids,
                "folder_names": spec.folder_names,
                "tags": spec.tags,
                "tag_mode": spec.tag_mode,
                "text_query": spec.text_query,
                "keyword_mode": spec.keyword_mode,
                "regex": spec.regex,
                "exclude_regex": spec.exclude_regex,
                "search_fields": fields,
                "due_from": spec.due_from,
                "due_to": spec.due_to,
                "start_from": spec.start_from,
                "start_to": spec.start_to,
                "modified_from": spec.modified_from,
                "modified_to": spec.modified_to,
                "created_from": spec.created_from,
                "created_to": spec.created_to,
                "time_from": spec.time_from,
                "time_to": spec.time_to,
                "timed_only": spec.timed_only,
                "all_day": spec.all_day,
                "min_priority": spec.min_priority,
                "priorities": spec.priorities,
                "has_reminders": spec.has_reminders,
                "is_recurring": spec.is_recurring,
                "has_checklist": spec.has_checklist,
                "parent_only": spec.parent_only,
                "subtasks_only": spec.subtasks_only,
                "sort_by": spec.sort_by,
                "descending": spec.descending,
            },
        }

    def _match_task_filters(
        self,
        task: Task,
        meta: dict[str, Any],
        spec: TaskFilterSpec,
        fields: list[str],
        compiled_regex: Optional[re.Pattern[str]],
        exclude_regex: Optional[re.Pattern[str]],
    ) -> bool:
        if spec.project_ids and task.projectId not in spec.project_ids:
            return False
        if spec.project_names and (meta.get("project_name") or "").lower() not in {name.lower() for name in spec.project_names}:
            return False
        if spec.folder_ids and meta.get("folder_id") not in spec.folder_ids:
            return False
        if spec.folder_names and (meta.get("folder_name") or "").lower() not in {name.lower() for name in spec.folder_names}:
            return False
        if spec.tags and not self._match_tags(task.tags, spec.tags, spec.tag_mode):
            return False
        if spec.priorities and task.priority not in spec.priorities:
            return False
        if spec.min_priority is not None and task.priority < spec.min_priority:
            return False
        if spec.has_reminders is not None and bool(task.reminders) != spec.has_reminders:
            return False
        if spec.is_recurring is not None and bool(task.effective_repeat()) != spec.is_recurring:
            return False
        if spec.has_checklist is not None and bool(task.items) != spec.has_checklist:
            return False
        if spec.parent_only and task.parentId:
            return False
        if spec.subtasks_only and not task.parentId:
            return False

        all_day = task.effective_all_day()
        if spec.all_day is not None and all_day != spec.all_day:
            return False
        if spec.timed_only and (all_day is True or not self._scheduled_time(task)):
            return False
        if not self._match_time_window(task, spec.time_from, spec.time_to):
            return False

        if not self._match_datetime_window(task.dueDate, spec.due_from, spec.due_to):
            return False
        if not self._match_datetime_window(task.startDate, spec.start_from, spec.start_to):
            return False
        if not self._match_datetime_window(task.modifiedTime, spec.modified_from, spec.modified_to):
            return False
        if not self._match_datetime_window(task.createdTime, spec.created_from, spec.created_to):
            return False

        blob = self._task_blob(task, meta, fields)
        if not self._match_search(blob, spec.text_query, spec.keyword_mode, compiled_regex, exclude_regex, fields):
            return False
        return True

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------
    def _match_tags(self, actual_tags: list[str], wanted_tags: list[str], mode: str) -> bool:
        actual = {tag.lower() for tag in actual_tags}
        wanted = {tag.lower() for tag in wanted_tags}
        if not wanted:
            return True
        if mode == "all":
            return wanted.issubset(actual)
        return bool(actual & wanted)

    def _match_search(
        self,
        blob: str,
        text_query: Optional[str],
        keyword_mode: str,
        regex: Optional[re.Pattern[str] | str],
        exclude_regex: Optional[re.Pattern[str] | str],
        _fields: list[str],
    ) -> bool:
        lowered = blob.lower()
        if text_query:
            query = text_query.strip().lower()
            if keyword_mode == "phrase":
                if query not in lowered:
                    return False
            else:
                tokens = [token for token in re.split(r"\s+", query) if token]
                if keyword_mode == "all":
                    if not all(token in lowered for token in tokens):
                        return False
                else:
                    if tokens and not any(token in lowered for token in tokens):
                        return False

        if regex:
            compiled = regex if isinstance(regex, re.Pattern) else re.compile(regex, re.IGNORECASE)
            if not compiled.search(blob):
                return False
        if exclude_regex:
            compiled = exclude_regex if isinstance(exclude_regex, re.Pattern) else re.compile(exclude_regex, re.IGNORECASE)
            if compiled.search(blob):
                return False
        return True

    def _match_datetime_window(self, value: Optional[str], lower: Optional[str], upper: Optional[str]) -> bool:
        if not lower and not upper:
            return True
        dt = self._parse_datetime(value)
        if dt is None:
            return False
        if lower:
            lower_dt = self._parse_bound(lower, end=False)
            if lower_dt and dt < lower_dt:
                return False
        if upper:
            upper_dt = self._parse_bound(upper, end=True)
            if upper_dt and dt > upper_dt:
                return False
        return True

    def _match_time_window(self, task: Task, time_from: Optional[str], time_to: Optional[str]) -> bool:
        if not time_from and not time_to:
            return True
        scheduled = self._scheduled_time(task)
        if scheduled is None:
            return False
        start = self._parse_clock_time(time_from) if time_from else None
        end = self._parse_clock_time(time_to) if time_to else None
        if start and scheduled < start:
            return False
        if end and scheduled > end:
            return False
        return True

    def _scheduled_time(self, task: Task) -> Optional[time]:
        dt = self._parse_datetime(task.dueDate) or self._parse_datetime(task.startDate)
        if dt is None:
            return None
        return dt.timetz().replace(tzinfo=None)

    def _row_matches_agenda_window(self, row: dict[str, Any], from_dt: str, to_dt: str, date_field: str) -> bool:
        lower = self._parse_bound(from_dt, end=False)
        upper = self._parse_bound(to_dt, end=True)
        candidates: list[Optional[datetime]]
        if date_field == "due":
            candidates = [self._parse_datetime(row.get("dueDate"))]
        elif date_field == "start":
            candidates = [self._parse_datetime(row.get("startDate"))]
        else:
            candidates = [
                self._parse_datetime(row.get("dueDate")),
                self._parse_datetime(row.get("startDate")),
            ]

        for candidate in candidates:
            if candidate is None:
                continue
            if lower and candidate < lower:
                continue
            if upper and candidate > upper:
                continue
            return True
        return False

    # ------------------------------------------------------------------
    # Blob and sort helpers
    # ------------------------------------------------------------------
    def _task_blob(self, task: Task, meta: dict[str, Any], fields: list[str]) -> str:
        values: list[str] = []
        for field in fields:
            if field == "title":
                values.append(task.title or "")
            elif field == "content":
                values.append(task.content or "")
            elif field == "desc":
                values.append(task.desc or "")
            elif field == "tags":
                values.append(" ".join(task.tags or []))
            elif field == "project":
                values.append(meta.get("project_name") or "")
            elif field == "folder":
                values.append(meta.get("folder_name") or "")
        return " \n".join(values)

    def _project_blob(self, project: Project, meta: dict[str, Any]) -> str:
        return f"{project.name or ''}\n{meta.get('folder_name') or ''}"

    def _folder_blob(self, folder: ProjectGroup) -> str:
        return folder.name or ""

    def _task_sort_key(self, row: dict[str, Any], sort_by: str) -> tuple[int, Any]:
        field = sort_by if sort_by in VALID_TASK_SORT_FIELDS else "dueDate"
        if field == "priority":
            return (0, row.get("priority") or 0)
        if field == "title":
            return (0, (row.get("title") or "").lower())
        if field == "project":
            return (0, (row.get("project_name") or "").lower())
        if field == "folder":
            return (0, (row.get("folder_name") or "").lower())
        dt = self._parse_datetime(row.get(field))
        return (0 if dt is not None else 1, dt.timestamp() if dt is not None else float("inf"))

    def _project_sort_key(self, row: dict[str, Any], sort_by: str) -> Any:
        if sort_by == "folder":
            return (row.get("folder_name") or "").lower(), (row.get("name") or "").lower()
        return (row.get("name") or "").lower()

    # ------------------------------------------------------------------
    # Datetime helpers
    # ------------------------------------------------------------------
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        if re.match(r".*[+-]\d{4}$", raw):
            raw = f"{raw[:-5]}{raw[-5:-2]}:{raw[-2:]}"
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    def _parse_bound(self, raw: str, end: bool) -> Optional[datetime]:
        raw = raw.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            only_date = date.fromisoformat(raw)
            if end:
                return datetime.combine(only_date, time(23, 59, 59))
            return datetime.combine(only_date, time(0, 0, 0))
        parsed = self._parse_datetime(raw)
        if parsed is not None:
            return parsed
        return None

    def _parse_clock_time(self, raw: str) -> time:
        parts = raw.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time '{raw}'. Expected HH:MM.")
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour=hour, minute=minute)
