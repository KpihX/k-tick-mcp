"""
Script 6 / 8 — Tags
Tests : list_tags, create_tag, update_tag, rename_tag, merge_tags, delete_tag
Toutes les ressources créées sont SUPPRIMÉES à la fin.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from k_tick_mcp.server import (
    list_tags, create_tag, update_tag, rename_tag, merge_tags, delete_tag,
)

_header("6/8 — Tags")

created_tags: list[str] = []  # noms des tags créés

# ── 0. Nettoyage initial — supprimer les tags résiduels de runs précédents ─
_leftover_names = [
    "test-tag-alpha", "test-tag-beta", "test-tag-gamma",
    "test-tag-gamma-renamed",
]
for _n in _leftover_names:
    try:
        delete_tag(tag_name=_n)
    except Exception:
        pass
import time; time.sleep(0.3)  # laisser l'API digérer

# ── 1. list_tags ──────────────────────────────────────────────────────────────
r = check("list_tags()", list_tags)
assert_result("  retourne liste", r, r is not None and isinstance(r, list))
if r:
    print(f"    → {len(r)} tag(s) existants: {[t.get('name') for t in r]}")

# ── 2. create_tag — minimal ───────────────────────────────────────────────────
r = check("create_tag(minimal)",
          lambda: create_tag(name="test-tag-alpha"))
if r and isinstance(r, dict) and not r.get("error"):
    created_tags.append("test-tag-alpha")
    assert_result("  API ok (tag créé)", r, not r.get("error"))

# ── 3. create_tag — avec couleur ─────────────────────────────────────────────
r = check("create_tag(avec couleur)",
          lambda: create_tag(name="test-tag-beta", color="#FF6161"))
if r and isinstance(r, dict) and not r.get("error"):
    created_tags.append("test-tag-beta")

# ── 4. create_tag — avec sortOrder ───────────────────────────────────────────
r = check("create_tag(avec sortType)",
          lambda: create_tag(name="test-tag-gamma", sort_type="dueDate"))
if r and isinstance(r, dict) and not r.get("error"):
        created_tags.append("test-tag-gamma")

# ── 5. create_tag — doublon (doit être gracieux) ─────────────────────────────
if "test-tag-alpha" in created_tags:
    r = check("create_tag(doublon)", lambda: create_tag(name="test-tag-alpha"),
              expect_no_error=False)
    assert_result("  pas de crash", r, r is not None)

# ── 6. create_tag — nom vide ─────────────────────────────────────────────────
r = check("create_tag(nom vide)", lambda: create_tag(name=""),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 7. update_tag ────────────────────────────────────────────────────────────
if "test-tag-alpha" in created_tags:
    r = check("update_tag(couleur)",
              lambda: update_tag(name="test-tag-alpha", color="#35D870"))
    assert_result("  pas de crash", r, r is not None)

# ── 8. update_tag — tag inexistant ───────────────────────────────────────────
r = check("update_tag(non existant)", lambda: update_tag(name="tag-qui-nexiste-pas", color="#000"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 9. rename_tag ────────────────────────────────────────────────────────────
if "test-tag-gamma" in created_tags:
    r = check("rename_tag(gamma → gamma-renamed)",
              lambda: rename_tag(old_name="test-tag-gamma", new_name="test-tag-gamma-renamed"))
    if r and isinstance(r, dict) and not r.get("error"):
        created_tags.remove("test-tag-gamma")
        created_tags.append("test-tag-gamma-renamed")
    assert_result("  pas de crash", r, r is not None)

# ── 10. rename_tag — ancien nom inexistant ────────────────────────────────────
r = check("rename_tag(old inexistant)", lambda: rename_tag(old_name="no-such-tag", new_name="x"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 11. merge_tags ────────────────────────────────────────────────────────────
# merge beta → alpha (beta disparaît, alpha absorbe)
if "test-tag-alpha" in created_tags and "test-tag-beta" in created_tags:
    r = check("merge_tags(beta → alpha)",
              lambda: merge_tags(source_name="test-tag-beta", target_name="test-tag-alpha"))
    if r and isinstance(r, dict) and not r.get("error"):
        created_tags.remove("test-tag-beta")
    assert_result("  pas de crash", r, r is not None)

# ── 12. merge_tags — source inexistante ──────────────────────────────────────
r = check("merge_tags(source inexistante)",
          lambda: merge_tags(source_name="no-such-tag-zzz", target_name="test-tag-alpha"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── NETTOYAGE ─────────────────────────────────────────────────────────────────
print(f"\n    {INFO} Nettoyage tags: {created_tags}{RESET}")
for tag_name in list(created_tags):
    r = check(f"delete_tag({tag_name})", lambda n=tag_name: delete_tag(tag_name=n))
    if r is not None:
        created_tags.remove(tag_name)

# ── 13. delete_tag — nom inexistant ──────────────────────────────────────────
r = check("delete_tag(non existant)", lambda: delete_tag(tag_name="this-tag-does-not-exist"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

summary()
