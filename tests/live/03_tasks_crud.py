"""
Script 3 / 8 — Tâches CRUD
Tests : create_task (many variants), update_task, complete_task,
        reopen_task, delete_task
Toutes les tâches créées sont SUPPRIMÉES à la fin.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from k_tick_mcp.server import (
    create_task, update_task, complete_task, reopen_task, delete_task,
    get_task_detail, list_projects,
)

_header("3/8 — Tâches CRUD")

created: list[dict] = []  # pour nettoyer à la fin

projs = list_projects() or []
task_proj = next((p for p in projs if p.get("kind") == "TASK" and not p.get("closed")), None)
test_pid = task_proj["id"] if task_proj else None
test_proj_name = task_proj["name"] if task_proj else "Inbox"

# ── HELPER ───────────────────────────────────────────────────────────────────
def make(label: str, **kwargs):
    r = check(f"create_task({label})", lambda: create_task(**kwargs))
    if r and isinstance(r, dict) and r.get("id"):
        created.append({"id": r["id"], "projectId": r.get("projectId","")})
        assert_result(f"  a un id",    r, bool(r.get("id")))
        assert_result(f"  a un title", r, bool(r.get("title")))
    return r

# ── 1. create_task — minimal ─────────────────────────────────────────────────
r = make("minimal", title="[TEST] tâche minimale")
if r:
    assert_result("  projectId = inbox ou null", r,
                  r.get("projectId","").startswith("inbox") or not r.get("projectId"))

# ── 2. create_task — dans un projet ─────────────────────────────────────────
if test_pid:
    r = make("dans projet", title=f"[TEST] tâche dans {test_proj_name}", project_id=test_pid)
    if r:
        assert_result("  bon projectId", r, r.get("projectId") == test_pid)

# ── 3. create_task — avec dueDate ────────────────────────────────────────────
r = make("avec dueDate", title="[TEST] tâche avec date",
         due_date="2026-12-31T09:00:00+0000")
if r:
    assert_result("  dueDate présent", r, bool(r.get("dueDate")))

# ── 4. create_task — priorité high ───────────────────────────────────────────
r = make("priority high", title="[TEST] priorité haute", priority=3)
if r:
    assert_result("  priority == 3", r, r.get("priority") == 3)

# ── 5. create_task — avec contenu ────────────────────────────────────────────
r = make("avec content", title="[TEST] avec contenu",
         content="Ligne 1\nLigne 2\nLigne 3")
if r:
    assert_result("  content présent", r, bool(r.get("content")))

# ── 6. create_task — avec items (checklist) ──────────────────────────────────
r = make("checklist", title="[TEST] checklist",
         checklist_items=["sous-tâche A", "sous-tâche B", "sous-tâche C"])
if r:
    assert_result("  items présents", r, len(r.get("items", [])) >= 1)

# ── 7. create_task — tâche récurrente daily ──────────────────────────────────
r = make("récurrente daily", title="[TEST] récurrente daily",
         recurrence="RRULE:FREQ=DAILY;INTERVAL=1",
         start_date="2026-01-01T09:00:00+0000")
if r:
    assert_result("  repeatFlag présent", r, bool(r.get("repeatFlag") or r.get("repeat")))

# ── 8. create_task — tags ────────────────────────────────────────────────────
r = make("avec tag", title="[TEST] avec tag", tags=["gcal"])
if r:
    assert_result("  tag gcal présent", r, "gcal" in r.get("tags", []))

# ── 9. create_task — title vide (doit retourner erreur grace) ────────────────
r = check("create_task(title vide)", lambda: create_task(title=""),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 10. create_task — startDate + allDay ─────────────────────────────────────
r = make("allDay + startDate", title="[TEST] allDay",
         start_date="2026-06-01T00:00:00+0000", all_day=True)

# ── 11. update_task — changer le titre ───────────────────────────────────────
if created:
    t = created[0]
    tid, tpid = t["id"], t["projectId"]
    r = check("update_task(titre+content)",
              lambda: update_task(task_id=tid, project_id=tpid or None,
                                  title="[TEST] titre mis à jour", content="Contenu mis à jour"))
    if r:
        assert_result("  title mis à jour", r, "[TEST] titre mis à jour" in str(r.get("title","")))

# ── 12. update_task — changer priorité ───────────────────────────────────────
if len(created) >= 2:
    t = created[1]
    r = check("update_task(priority 5)",
              lambda: update_task(task_id=t["id"], project_id=t["projectId"] or None, priority=5))
    if r:
        assert_result("  priority == 5", r, r.get("priority") == 5)

# ── 13. update_task — id invalide ────────────────────────────────────────────
r = check("update_task(invalid id)", lambda: update_task(task_id="badid111", project_id="badpid111", title="x"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 14. complete_task ─────────────────────────────────────────────────────────
if created:
    t = created[-1]
    r = check("complete_task()", lambda: complete_task(task_id=t["id"], project_id=t["projectId"] or None))
    # success peut être un dict vide ou avec status
    assert_result("  pas de crash", r, r is not None)

# ── 15. reopen_task ───────────────────────────────────────────────────────────
if created:
    t = created[-1]
    r = check("reopen_task()", lambda: reopen_task(task_id=t["id"], project_id=t["projectId"] or None))
    assert_result("  pas de crash", r, r is not None)

# ── 16. complete_task — id invalide ──────────────────────────────────────────
r = check("complete_task(invalid)", lambda: complete_task(project_id="badpid999", task_id="badid999"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── NETTOYAGE ─────────────────────────────────────────────────────────────────
print(f"\n    {INFO} Nettoyage : suppression de {len(created)} tâches de test...{RESET}")
deleted = 0
for t in created:
    try:
        r = delete_task(task_id=t["id"], project_id=t.get("projectId") or None)
        deleted += 1
    except Exception as e:
        print(f"    ⚠ delete {t['id'][:8]}... : {e}")

# ── 17. delete_task — id invalide ────────────────────────────────────────────
r = check("delete_task(invalid id)", lambda: delete_task(project_id="badpid_xxx", task_id="badid_xxx"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

print(f"    {INFO} {deleted}/{len(created)} tâches supprimées{RESET}")
summary()
