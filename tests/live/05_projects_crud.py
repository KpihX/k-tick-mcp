"""
Script 5 / 8 — Projets CRUD + Dossiers + Colonnes Kanban
Tests : create_project, update_project, delete_project,
        list_project_folders, manage_project_folders,
        list_columns, manage_columns
Toutes les ressources créées sont SUPPRIMÉES à la fin.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from ticktick_mcp.server import (
    create_project, update_project, delete_project,
    list_project_folders, manage_project_folders,
    list_columns, manage_columns, list_projects,
)

_header("5/8 — Projets CRUD + Dossiers + Colonnes")

created_projects: list[str] = []
created_folders:  list[str] = []

# ── 1. create_project — TASK minimal ─────────────────────────────────────────
r = check("create_project(TASK minimal)", lambda: create_project(name="[TEST] Proj Task"))
if r and isinstance(r, dict) and r.get("id"):
    created_projects.append(r["id"])
    assert_result("  name présent",  r, "[TEST]" in r.get("name", ""))
    assert_result("  kind = TASK",   r, r.get("kind", "TASK") == "TASK")

# ── 2. create_project — NOTE avec couleur ────────────────────────────────────
r = check("create_project(NOTE + couleur)",
          lambda: create_project(name="[TEST] Proj Note", kind="NOTE", color="#FF6161"))
if r and isinstance(r, dict) and r.get("id"):
    created_projects.append(r["id"])
    assert_result("  kind = NOTE", r, r.get("kind") == "NOTE")

# ── 3. create_project — viewMode kanban ──────────────────────────────────────
r = check("create_project(kanban viewMode)",
          lambda: create_project(name="[TEST] Proj Kanban", view_mode="kanban"))
kanban_pid = None
if r and isinstance(r, dict) and r.get("id"):
    kanban_pid = r["id"]
    created_projects.append(r["id"])

# ── 4. create_project — nom vide (edge case) ─────────────────────────────────
r = check("create_project(nom vide)", lambda: create_project(name=""),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 5. update_project ────────────────────────────────────────────────────────
if created_projects:
    pid = created_projects[0]
    r = check("update_project(name + color)",
              lambda: update_project(project_id=pid, name="[TEST] Proj MODIFIÉ",
                                     color="#35D870"))
    if r:
        assert_result("  nom mis à jour", r, "MODIFIÉ" in str(r.get("name","")))

# ── 6. update_project — view_mode list ───────────────────────────────────────
if created_projects:
    pid = created_projects[0]
    r = check("update_project(view_mode=list)",
              lambda: update_project(project_id=pid, view_mode="list"))
    assert_result("  pas de crash", r, r is not None)

# ── 7. update_project — id invalide ──────────────────────────────────────────
r = check("update_project(invalid id)", lambda: update_project(project_id="badbadid"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 8. list_project_folders ───────────────────────────────────────────────────
r = check("list_project_folders()", list_project_folders)
assert_result("  retourne liste", r, r is not None and isinstance(r, list))

# ── 9. manage_project_folders — créer ────────────────────────────────────────
r = check("manage_project_folders(create)",
          lambda: manage_project_folders(
              add=[{"name": "[TEST] Dossier A"}]
          ))
if r and isinstance(r, dict):
    # API may return {id2etag: {id: etag}} — extract folder ids for cleanup
    folder_ids = list((r.get("id2etag") or {}).keys())
    for fid in folder_ids:
        created_folders.append(fid)
    assert_result("  dossier créé (API ok)", r, not r.get("error"))

# ── 10. manage_project_folders — mettre à jour ───────────────────────────────
if created_folders:
    fid = created_folders[0]
    r = check("manage_project_folders(update)",
              lambda: manage_project_folders(
                  update=[{"id": fid, "name": "[TEST] Dossier MODIFIÉ"}]
              ))
    assert_result("  pas de crash", r, r is not None)

# ── 11. manage_project_folders — opérations mixtes vides ─────────────────────
r = check("manage_project_folders(rien)", lambda: manage_project_folders(),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 12. list_columns ──────────────────────────────────────────────────────────
# utilise le projet kanban créé ou premier projet TASK existant
projs = list_projects() or []
task_proj = next((p for p in projs if p.get("kind") == "TASK" and not p.get("closed")), None)
col_pid = kanban_pid or (task_proj["id"] if task_proj else None)

if col_pid:
    r = check(f"list_columns({col_pid[:8]}...)", lambda: list_columns(project_id=col_pid))
    assert_result("  retourne liste ou dict", r, r is not None)
else:
    check("list_columns", lambda: None, skip_reason="pas de projet TASK disponible")

# ── 13. manage_columns — créer des colonnes kanban ───────────────────────────
if col_pid:
    r = check("manage_columns(create 2 colonnes)",
              lambda: manage_columns(
                  project_id=col_pid,
                  add=[{"name": "[TEST] Col Todo"}, {"name": "[TEST] Col Done"}]
              ))
    assert_result("  pas de crash", r, r is not None)
    col_ids = []
    if r and isinstance(r, dict):
        for c in r.get("added", []) or []:
            if c.get("id"):
                col_ids.append(c["id"])

    # update colonne
    if col_ids:
        r2 = check("manage_columns(update colonne)",
                   lambda: manage_columns(
                       project_id=col_pid,
                       update=[{"id": col_ids[0], "name": "[TEST] Col Updated"}]
                   ))
        assert_result("  pas de crash", r2, r2 is not None)

        # delete colonnes
        r3 = check("manage_columns(delete colonnes)",
                   lambda: manage_columns(
                       project_id=col_pid,
                       delete=col_ids
                   ))
        assert_result("  pas de crash", r3, r3 is not None)

# ── NETTOYAGE ─────────────────────────────────────────────────────────────────
print(f"\n    {INFO} Nettoyage dossiers ({len(created_folders)})...{RESET}")
if created_folders:
    r = manage_project_folders(delete=created_folders)

print(f"    {INFO} Nettoyage projets ({len(created_projects)})...{RESET}")
del_ok = 0
for pid in created_projects:
    try:
        r = delete_project(project_id=pid)
        del_ok += 1
    except Exception as e:
        print(f"    ⚠ delete_project {pid[:8]}...: {e}")

# ── 14. delete_project — id invalide ─────────────────────────────────────────
r = check("delete_project(invalid id)", lambda: delete_project(project_id="badprojectid"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

print(f"    {INFO} {del_ok}/{len(created_projects)} projets supprimés{RESET}")
summary()
