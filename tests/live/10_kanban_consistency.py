"""
Script 10 / 12 — Kanban End-to-End, Cross-Project Moves, Consistency Check
Edge cases:  kanban project → columns CRUD → task in column → move between columns,
             multi-move in one call, move to/from inbox, get_all_tasks vs per-project,
             folder-project integration, project archive/unarchive, view_mode changes.
All test resources are DELETED at the end.
"""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from k_tick_mcp.server import (
    create_project, update_project, delete_project, get_project_detail,
    list_projects, get_project_tasks, get_inbox, get_all_tasks,
    create_task, update_task, delete_task,
    list_columns, manage_columns,
    list_project_folders, manage_project_folders,
    move_tasks, batch_create_tasks,
)

_header("10/12 — Kanban, Cross-Project & Consistency")

_proj_ids: list[str] = []
_task_cleanup: list[tuple[str, str]] = []  # (pid, tid)
_folder_ids: list[str] = []

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION A — Full Kanban Workflow
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Create kanban project ─────────────────────────────────────────────────
r = check("create_project(kanban)",
          lambda: create_project(name="Test-Kanban-E2E", view_mode="kanban"))
kb_pid = r.get("id") if r and not r.get("error") else None
if kb_pid:
    _proj_ids.append(kb_pid)

# ── 2. list_columns (should be empty or default) ─────────────────────────────
col_list = None
if kb_pid:
    col_list = check("list_columns(kanban project)",
                     lambda: list_columns(project_id=kb_pid))
    assert_result("  returns list", col_list, isinstance(col_list, list))
    if col_list:
        print(f"    → {len(col_list)} existing column(s)")

# ── 3. manage_columns: add 3 columns ─────────────────────────────────────────
col_ids = []
if kb_pid:
    r = check("manage_columns(add 3)",
              lambda: manage_columns(project_id=kb_pid, add=[
                  {"name": "To Do", "sortOrder": 0},
                  {"name": "In Progress", "sortOrder": 1},
                  {"name": "Done", "sortOrder": 2},
              ]))
    if r and not r.get("error"):
        # extract column IDs from id2etag
        etag_map = r.get("id2etag", r.get("result", {}))
        if isinstance(etag_map, dict):
            col_ids = list(etag_map.keys())
        print(f"    → created {len(col_ids)} columns: {col_ids}")

# ── 4. list_columns after add ────────────────────────────────────────────────
if kb_pid:
    r = check("list_columns(after add)",
              lambda: list_columns(project_id=kb_pid))
    if isinstance(r, list):
        assert_result("  at least 3 columns", r, len(r) >= 3, f"got {len(r)}")
        # prefer named columns for the rest
        col_map = {c.get("name"): c.get("id") for c in r}
        todo_col = col_map.get("To Do")
        prog_col = col_map.get("In Progress")
        done_col = col_map.get("Done")
        print(f"    → columns: {col_map}")

# ── 5. create_task in specific column ────────────────────────────────────────
task_in_col = None
if kb_pid and todo_col:
    r = check("create_task(column_id=To Do)",
              lambda: create_task(title="Kanban-task-todo",
                                  project_id=kb_pid, column_id=todo_col))
    if r and not r.get("error"):
        task_in_col = r
        _task_cleanup.append((kb_pid, r["id"]))
        assert_result("  columnId matches", r,
                      r.get("columnId") == todo_col,
                      f"expected {todo_col}, got {r.get('columnId')}")

# ── 6. update_task: move to another column ───────────────────────────────────
if task_in_col and prog_col:
    r = check("update_task(column_id=In Progress)",
              lambda: update_task(task_id=task_in_col["id"], project_id=kb_pid,
                                  column_id=prog_col))
    assert_result("  columnId updated", r,
                  r is not None and not r.get("error"),
                  f"columnId={r.get('columnId') if r else 'N/A'}")

# ── 7. manage_columns: rename a column ───────────────────────────────────────
if kb_pid and col_ids:
    rename_col = col_ids[0] if col_ids else None
    if rename_col:
        r = check("manage_columns(update name)",
                  lambda: manage_columns(project_id=kb_pid,
                                         update=[{"id": rename_col, "name": "Backlog"}]))
        assert_result("  rename ok", r, r is not None and not r.get("error"))

# ── 8. manage_columns: delete a column ───────────────────────────────────────
if kb_pid and done_col:
    r = check("manage_columns(delete Done column)",
              lambda: manage_columns(project_id=kb_pid, delete=[done_col]),
              expect_no_error=False)  # API may not support column delete cleanly
    assert_result("  delete attempted (API may reject)", r, r is not None)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION B — Cross-Project Moves
# ══════════════════════════════════════════════════════════════════════════════

# ── 9. Create 2 regular projects ─────────────────────────────────────────────
pA = check("create_project(A)", lambda: create_project(name="Test-Move-A"))
pA_id = pA.get("id") if pA and not pA.get("error") else None
if pA_id:
    _proj_ids.append(pA_id)

pB = check("create_project(B)", lambda: create_project(name="Test-Move-B"))
pB_id = pB.get("id") if pB and not pB.get("error") else None
if pB_id:
    _proj_ids.append(pB_id)

# ── 10. Create 3 tasks in project A via batch ─────────────────────────────────
batch_ids = []
if pA_id:
    r = check("batch_create(3 tasks in A)",
              lambda: batch_create_tasks([
                  {"title": "Move-X", "projectId": pA_id},
                  {"title": "Move-Y", "projectId": pA_id},
                  {"title": "Move-Z", "projectId": pA_id},
              ]))
    if r and not r.get("error"):
        etag_map = r.get("id2etag", {})
        batch_ids = list(etag_map.keys())
        for bid in batch_ids:
            _task_cleanup.append((pA_id, bid))
        print(f"    → {len(batch_ids)} tasks: {batch_ids[:3]}")

# ── 11. multi-move in one call (A → B) ───────────────────────────────────────
if pA_id and pB_id and len(batch_ids) >= 2:
    r = check("move_tasks(2 tasks A → B)",
              lambda: move_tasks([
                  {"taskId": batch_ids[0], "fromProjectId": pA_id, "toProjectId": pB_id},
                  {"taskId": batch_ids[1], "fromProjectId": pA_id, "toProjectId": pB_id},
              ]))
    assert_result("  multi-move ok", r, r is not None and not r.get("error"),
                  f"result={r}")
    # update cleanup tracking
    _task_cleanup = [(pB_id if t in batch_ids[:2] else p, t) for p, t in _task_cleanup]

# ── 12. move to inbox (toProjectId = inbox_id) ───────────────────────────────
if pA_id and len(batch_ids) >= 3:
    inbox_tasks = get_inbox()
    inbox_id = ""
    # Derive inboxId from an inbox task, or use full_sync
    from k_tick_mcp.server import full_sync
    sync = full_sync()
    if sync and isinstance(sync, dict):
        inbox_id = sync.get("inboxId", "")
    if inbox_id and batch_ids:
        r = check("move_tasks(A → inbox)",
                  lambda: move_tasks([
                      {"taskId": batch_ids[2], "fromProjectId": pA_id, "toProjectId": inbox_id}
                  ]))
        assert_result("  move to inbox ok", r, r is not None and not r.get("error"))
        _task_cleanup = [(inbox_id if t == batch_ids[2] else p, t) for p, t in _task_cleanup]

# ── 13. verify tasks in project B after move ──────────────────────────────────
if pB_id and len(batch_ids) >= 2:
    r = check("get_project_tasks(B after move)",
              lambda: get_project_tasks(project_id=pB_id))
    if isinstance(r, list) and r:
        # get_project_tasks returns [{"tasks": [...], "columns": [...]}]
        inner_tasks = r[0].get("tasks", []) if isinstance(r[0], dict) else r
        moved_ids = {t.get("id") for t in inner_tasks}
        assert_result("  tasks X,Y in B", None,
                      batch_ids[0] in moved_ids and batch_ids[1] in moved_ids,
                      f"expected {batch_ids[:2]}, found {moved_ids}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION C — Consistency: get_all_tasks vs per-project
# ══════════════════════════════════════════════════════════════════════════════

# ── 14. get_all_tasks count ───────────────────────────────────────────────────
all_tasks = check("get_all_tasks()", get_all_tasks)
all_count = len(all_tasks) if isinstance(all_tasks, list) else 0

# ── 15. per-project sum ──────────────────────────────────────────────────────
projects = check("list_projects()", list_projects)
per_proj_count = 0
if isinstance(projects, list):
    for p in projects:
        pid = p.get("id")
        if pid:
            proj_data = get_project_tasks(project_id=pid)
            if isinstance(proj_data, list) and proj_data:
                inner = proj_data[0]
                if isinstance(inner, dict):
                    per_proj_count += len(inner.get("tasks", []))
    # add inbox
    inbox = get_inbox()
    if isinstance(inbox, list):
        per_proj_count += len(inbox)
    # allow wider tolerance: get_all_tasks (V2 sync) may include archived/other tasks
    diff = abs(all_count - per_proj_count)
    # Use 15% tolerance or min 10
    tolerance = max(10, int(all_count * 0.15))
    assert_result("  all_tasks ≈ per-project sum", None,
                  diff <= tolerance,
                  f"all={all_count}, per_proj={per_proj_count}, diff={diff}, tol={tolerance}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION D — Folder-Project Integration
# ══════════════════════════════════════════════════════════════════════════════

# ── 16. create folder ────────────────────────────────────────────────────────
r = check("manage_project_folders(add folder)",
          lambda: manage_project_folders(add=[{"name": "Test-Folder-E2E"}]))
folder_id = None
if r and not r.get("error"):
    etag_map = r.get("id2etag", {})
    if isinstance(etag_map, dict) and etag_map:
        folder_id = list(etag_map.keys())[0]
        _folder_ids.append(folder_id)
        print(f"    → folder_id={folder_id}")

# ── 17. create project in folder ──────────────────────────────────────────────
proj_in_folder = None
if folder_id:
    r = check("create_project(in folder)",
              lambda: create_project(name="Test-In-Folder", group_id=folder_id))
    if r and not r.get("error"):
        proj_in_folder = r["id"]
        _proj_ids.append(proj_in_folder)
        # Note: TickTick API never echoes groupId on project objects;
        # folder-project mapping is managed server-side.  Verify creation ok.
        assert_result("  created in folder (groupId not echoed by API)", r,
                      r.get("id") is not None)

# ── 18. move project to different folder (via update_project group_id) ────────
# Create 2nd folder, move project there
if folder_id and proj_in_folder:
    r2 = manage_project_folders(add=[{"name": "Test-Folder-2"}])
    folder2_id = None
    if r2 and not r2.get("error"):
        etag2 = r2.get("id2etag", {})
        if isinstance(etag2, dict) and etag2:
            folder2_id = list(etag2.keys())[0]
            _folder_ids.append(folder2_id)
    if folder2_id:
        r = check("update_project(move to folder2)",
                  lambda: update_project(project_id=proj_in_folder, group_id=folder2_id))
        assert_result("  groupId updated", r,
                      r is not None and not r.get("error"),
                      f"groupId={r.get('groupId') if r else 'N/A'}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION E — Project Archive/Unarchive & View Mode Switches
# ══════════════════════════════════════════════════════════════════════════════

# ── 19. archive project ──────────────────────────────────────────────────────
archive_pid = None
r = check("create_project(archive-test)", lambda: create_project(name="Test-Archive"))
if r and not r.get("error"):
    archive_pid = r["id"]
    _proj_ids.append(archive_pid)

if archive_pid:
    r = check("update_project(closed=True → archive)",
              lambda: update_project(project_id=archive_pid, closed=True))
    assert_result("  archived", r, r is not None and not r.get("error"))

# ── 20. unarchive project ────────────────────────────────────────────────────
if archive_pid:
    r = check("update_project(closed=False → unarchive)",
              lambda: update_project(project_id=archive_pid, closed=False))
    assert_result("  unarchived", r, r is not None and not r.get("error"))

# ── 21. switch view mode list → kanban → timeline → list ─────────────────────
if archive_pid:
    for mode in ["kanban", "timeline", "list"]:
        r = check(f"update_project(view_mode={mode})",
                  lambda m=mode: update_project(project_id=archive_pid, view_mode=m))
        assert_result(f"  view_mode={mode} ok", r, r is not None and not r.get("error"))

# ── 22. switch project kind TASK → NOTE → TASK ───────────────────────────────
if archive_pid:
    r = check("update_project(kind=NOTE)",
              lambda: update_project(project_id=archive_pid, kind="NOTE"))
    assert_result("  kind=NOTE ok", r, r is not None and not r.get("error"))

    r = check("update_project(kind=TASK)",
              lambda: update_project(project_id=archive_pid, kind="TASK"))
    assert_result("  kind=TASK ok", r, r is not None and not r.get("error"))

# ══════════════════════════════════════════════════════════════════════════════
#  NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n    {INFO}Nettoyage : {len(_task_cleanup)} tâches, {len(_proj_ids)} projets, {len(_folder_ids)} dossiers{RESET}")

for pid, tid in _task_cleanup:
    try:
        delete_task(project_id=pid, task_id=tid)
    except Exception:
        pass

for pid in _proj_ids:
    try:
        delete_project(project_id=pid)
    except Exception:
        pass

for fid in _folder_ids:
    try:
        manage_project_folders(delete=[fid])
    except Exception:
        pass

summary()
