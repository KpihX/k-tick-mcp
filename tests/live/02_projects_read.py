"""
Script 2 / 8 — Projets (lecture seule)
Tests : list_projects, get_project_detail, get_inbox,
        get_project_tasks, get_task_detail
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from ticktick_mcp.server import (
    list_projects, get_project_detail, get_inbox,
    get_project_tasks, get_task_detail,
)

_header("2/8 — Projets (lecture)")

# ── 1. list_projects ──────────────────────────────────────────────────────────
projs = check("list_projects()", list_projects)
assert_result("  retourne liste", projs, isinstance(projs, list))
assert_result("  non vide",       projs, projs is not None and len(projs) > 0)
if projs:
    p0 = projs[0]
    for k in ("id","name","kind","closed"):
        assert_result(f"  projet a '{k}'", p0, k in p0)
    # collect useful project ids for next tests
    task_projs = [p for p in projs if p.get("kind") == "TASK" and not p.get("closed")]
    note_projs = [p for p in projs if p.get("kind") == "NOTE" and not p.get("closed")]
else:
    task_projs = []
    note_projs = []

# ── 2. get_project_detail — projet valide ────────────────────────────────────
if projs:
    pid = projs[0]["id"]
    r = check(f"get_project_detail(valid_id)", lambda: get_project_detail(pid))
    if r:
        assert_result("  id correspond", r, r.get("id") == pid or "tasks" in r or "name" in r)

# get_project_detail — id inexistant
r = check("get_project_detail(invalid_id)", lambda: get_project_detail("000000000000000000000000"),
          expect_no_error=False)
# should return error dict or empty, not crash
assert_result("  pas de crash", r, r is not None)

# ── 3. get_inbox ──────────────────────────────────────────────────────────────
# get_inbox retourne directement une list[dict]
r = check("get_inbox()", get_inbox)
if r is not None:
    assert_result("  retourne liste", r, isinstance(r, list))
    if r:
        assert_result("  tâche a 'id'",    r[0], "id" in r[0])
        assert_result("  tâche a 'title'", r[0], "title" in r[0])
    print(f"    → {len(r)} tâches inbox")
    inbox_tasks_list = r  # pour usage en dessous

# ── 4. get_project_tasks — TASK project ───────────────────────────────────────
if projs:
    task_proj = next((p for p in projs if p.get("kind") == "TASK"), projs[0])
    pid = task_proj["id"]
    pname = task_proj["name"]

    # sans complètes
    r = check(f"get_project_tasks({pname}, completed=False)",
              lambda: get_project_tasks(pid, include_completed=False))
    if r:
        tasks_list = r["tasks"] if isinstance(r, dict) else r
        assert_result("  pas de tâches complètes", tasks_list,
                      not any(t.get("is_completed") for t in (tasks_list if isinstance(tasks_list, list) else [])))

    # avec complètes
    r2 = check(f"get_project_tasks({pname}, completed=True)",
               lambda: get_project_tasks(pid, include_completed=True))

    # projet invalide
    r3 = check("get_project_tasks(invalid_id)", lambda: get_project_tasks("000000000000000000badid"),
               expect_no_error=False)
    assert_result("  pas de crash", r3, r3 is not None)

# ── 4b. get_project_tasks — NOTE project ─────────────────────────────────────
if note_projs:
    note_p = note_projs[0]
    r = check(f"get_project_tasks(NOTE:{note_p['name']})",
              lambda: get_project_tasks(note_p["id"]))
    # Notes peuvent avoir kind="NOTE" dans tasks
    if r:
        tasks_list = r.get("tasks", []) if isinstance(r, dict) else r
        print(f"    → {len(tasks_list)} notes")

# ── 5. get_task_detail ────────────────────────────────────────────────────────
# get_inbox() retourne list[dict] directement
inbox_tasks = get_inbox()
inbox_tasks = inbox_tasks if isinstance(inbox_tasks, list) else []

if inbox_tasks:
    t0  = inbox_tasks[0]
    tid = t0.get("id")
    pid = t0.get("projectId")
    if tid and pid:
        r = check("get_task_detail(inbox tâche, avec project_id)",
                  lambda: get_task_detail(task_id=tid, project_id=pid))
        if r and isinstance(r, dict) and not r.get("error"):
            for k in ("id","title","projectId"):
                assert_result(f"  tâche a '{k}'", r, k in r)



# id invalide
r = check("get_task_detail(invalid ids)",
          lambda: get_task_detail("badid123", "badpid123"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

summary()
