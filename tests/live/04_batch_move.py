"""
Script 4 / 8 — Batch & Relations
Tests : batch_create_tasks, batch_update_tasks, batch_delete_tasks,
        move_tasks, set_subtask_parent
Toutes les tâches créées sont SUPPRIMÉES à la fin.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from ticktick_mcp.server import (
    batch_create_tasks, batch_update_tasks, batch_delete_tasks,
    move_tasks, set_subtask_parent, list_projects,
)

_header("4/8 — Batch & Relations")

projs = list_projects() or []
task_projs = [p for p in projs if p.get("kind") == "TASK" and not p.get("closed")]
pid_a = task_projs[0]["id"] if len(task_projs) >= 1 else None
pid_b = task_projs[1]["id"] if len(task_projs) >= 2 else pid_a

batch_ids: list[dict] = []  # {id, projectId}

# ── 1. batch_create_tasks — liste normale ────────────────────────────────────
r = check("batch_create_tasks(3 tâches)",
          lambda: batch_create_tasks([
              {"title": "[BATCH] tâche 1", "projectId": pid_a},
              {"title": "[BATCH] tâche 2", "projectId": pid_a,
               "priority": 3, "content": "contenu batch"},
              {"title": "[BATCH] tâche 3", "projectId": pid_a,
               "dueDate": "2026-12-31T09:00:00+0000"},
          ]))
if r and isinstance(r, dict):
    created_ids = list((r.get("id2etag") or {}).keys())
    assert_result("  3 tâches créées", r, len(created_ids) >= 3)
    for tid in created_ids:
        batch_ids.append({"id": tid, "projectId": pid_a or ""})

# ── 2. batch_create_tasks — liste vide ───────────────────────────────────────
r = check("batch_create_tasks([])", lambda: batch_create_tasks([]),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 3. batch_create_tasks — sans projectId (inbox) ───────────────────────────
r = check("batch_create_tasks(sans projectId)",
          lambda: batch_create_tasks([
              {"title": "[BATCH] inbox A"},
              {"title": "[BATCH] inbox B"},
          ]))
if r and isinstance(r, dict):
    inbox_ids = list((r.get("id2etag") or {}).keys())
    for tid in inbox_ids:
        batch_ids.append({"id": tid, "projectId": ""})

# ── 4. batch_update_tasks ────────────────────────────────────────────────────
if len(batch_ids) >= 2:
    updates = [
        {"id": batch_ids[0]["id"], "projectId": batch_ids[0]["projectId"],
         "title": "[BATCH] tâche 1 — MODIFIÉE", "priority": 5},
        {"id": batch_ids[1]["id"], "projectId": batch_ids[1]["projectId"],
         "title": "[BATCH] tâche 2 — MODIFIÉE", "content": "mis à jour en batch"},
    ]
    r = check("batch_update_tasks(2 tâches)", lambda: batch_update_tasks(updates))
    assert_result("  pas de crash", r, r is not None)

# ── 5. batch_update_tasks — liste vide ───────────────────────────────────────
r = check("batch_update_tasks([])", lambda: batch_update_tasks([]),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 6. move_tasks ─────────────────────────────────────────────────────────────
if batch_ids and pid_b and pid_b != pid_a:
    t = batch_ids[0]
    r = check(f"move_tasks({t['id'][:8]}... vers {pid_b[:8]}...)",
              lambda: move_tasks([
                  {"taskId": t["id"], "fromProjectId": t["projectId"], "toProjectId": pid_b}
              ]))
    if r is not None:
        batch_ids[0]["projectId"] = pid_b
    assert_result("  pas de crash", r, r is not None)
else:
    check("move_tasks", lambda: None,
          skip_reason="besoin de 2 projets TASK différents")

# ── 7. move_tasks — liste vide ───────────────────────────────────────────────
if pid_a:
    r = check("move_tasks([])", lambda: move_tasks([]),
              expect_no_error=False)
    assert_result("  pas de crash", r, r is not None)

# ── 8. set_subtask_parent ─────────────────────────────────────────────────────
if len(batch_ids) >= 2:
    child = batch_ids[0]
    parent = batch_ids[1]
    r = check("set_subtask_parent(child, parent)",
              lambda: set_subtask_parent(
                  task_id=child["id"], project_id=child["projectId"],
                  parent_id=parent["id"]
              ))
    assert_result("  pas de crash", r, r is not None)

    # Enlever la relation parent
    r2 = check("set_subtask_parent(remove, old_parent_id)",
               lambda: set_subtask_parent(
                   task_id=child["id"], project_id=child["projectId"],
                   old_parent_id=parent["id"]
               ))
    assert_result("  pas de crash", r2, r2 is not None)

# ── 9. set_subtask_parent — id invalide ──────────────────────────────────────
r = check("set_subtask_parent(invalid ids)", lambda: set_subtask_parent(
    task_id="badid", project_id="badpid", parent_id="badparent"
), expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── NETTOYAGE ─────────────────────────────────────────────────────────────────
print(f"\n    {INFO} Nettoyage : suppression de {len(batch_ids)} tâches batch...{RESET}")
if batch_ids:
    delete_payload = [{"taskId": t["id"], "projectId": t["projectId"]} for t in batch_ids]
    try:
        r = check("batch_delete_tasks(toutes créées)",
                  lambda: batch_delete_tasks(delete_payload))
        assert_result("  pas de crash", r, r is not None)
    except Exception as e:
        print(f"    ⚠ batch_delete error: {e}")

# ── 10. batch_delete_tasks — liste vide ──────────────────────────────────────
r = check("batch_delete_tasks([])", lambda: batch_delete_tasks([]),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

summary()
