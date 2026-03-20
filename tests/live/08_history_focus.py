"""
Script 8 / 8 — Historique (completed/deleted) + Focus stats
Tests : get_completed_tasks, get_deleted_tasks, get_focus_stats
Lecture seule — aucune modification.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET
from datetime import date, timedelta

from ticktick_mcp.server import (
    get_completed_tasks, get_deleted_tasks, get_focus_stats,
)

_header("8/8 — Historique & Focus")

today = date.today()
d30 = (today - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
d7  = (today - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
now = today.strftime("%Y-%m-%d 23:59:59")

# ── 1. get_completed_tasks — 30 derniers jours ───────────────────────────────
r = check("get_completed_tasks(30j)",
          lambda: get_completed_tasks(from_date=d30, to_date=now))
if r is not None:
    assert_result("  retourne liste", r, isinstance(r, list))
    if r:
        t = r[0]
        assert_result("  tâche a 'id'",    t, "id" in t)
        assert_result("  tâche a 'title'", t, "title" in t)
        assert_result("  is_completed",    t, t.get("is_completed") == True)
    print(f"    → {len(r)} tâches complétées (30j)")

# ── 2. get_completed_tasks — 7 jours ─────────────────────────────────────────
r = check("get_completed_tasks(7j)",
          lambda: get_completed_tasks(from_date=d7, to_date=now))
if r is not None:
    assert_result("  retourne liste", r, isinstance(r, list))
    print(f"    → {len(r)} tâches complétées (7j)")

# ── 3. get_completed_tasks — limit variés ─────────────────────────────────────
for limit in (1, 10):
    r = check(f"get_completed_tasks(30j, limit={limit})",
              lambda l=limit: get_completed_tasks(from_date=d30, to_date=now, limit=l))
    if r is not None:
        assert_result(f"  <= {limit} résultats", r,
                      isinstance(r, list) and len(r) <= limit)

# ── 4. get_completed_tasks — status=Abandoned ────────────────────────────────
r = check("get_completed_tasks(Abandoned)",
          lambda: get_completed_tasks(from_date=d30, to_date=now, status="Abandoned"))
if r is not None:
    assert_result("  retourne liste", r, isinstance(r, list))
    print(f"    → {len(r)} tâches abandonnées (30j)")

# ── 5. get_completed_tasks — plage vide (future) ─────────────────────────────
future = "2030-01-01 00:00:00"
future_end = "2030-01-02 23:59:59"
r = check("get_completed_tasks(plage vide)",
          lambda: get_completed_tasks(from_date=future, to_date=future_end))
if r is not None:
    assert_result("  liste vide", r, isinstance(r, list) and len(r) == 0)

# ── 6. get_deleted_tasks — défaut ─────────────────────────────────────────────
r = check("get_deleted_tasks(défaut)", get_deleted_tasks)
if r is not None:
    assert_result("  retourne liste", r, isinstance(r, list))
    if r:
        t = r[0]
        assert_result("  tâche a 'id'",    t, "id" in t)
        assert_result("  tâche a 'title'", t, "title" in t)
    print(f"    → {len(r)} tâches supprimées")

# ── 7. get_deleted_tasks — limit ─────────────────────────────────────────────
for limit in (5, 20):
    r = check(f"get_deleted_tasks(limit={limit})",
              lambda l=limit: get_deleted_tasks(limit=l))
    if r is not None:
        assert_result(f"  <= {limit} résultats", r,
                      isinstance(r, list) and len(r) <= limit)

# ── 8. get_deleted_tasks — pagination (offset) ───────────────────────────────
r = check("get_deleted_tasks(start=0, limit=5)",
          lambda: get_deleted_tasks(start=0, limit=5))
page1 = r if isinstance(r, list) else []

r = check("get_deleted_tasks(start=5, limit=5)",
          lambda: get_deleted_tasks(start=5, limit=5))
page2 = r if isinstance(r, list) else []

if page1 and page2:
    ids1 = {t.get("id") for t in page1}
    ids2 = {t.get("id") for t in page2}
    overlap = ids1 & ids2
    # L'API deleted peut avoir un léger chevauchement — on tolère ≤ 2
    assert_result("  pages différentes", None,
                  len(overlap) <= 2, f"chevauchement: {overlap}")

# ── 9. get_focus_stats — heatmap (30j) ───────────────────────────────────────
fd30 = (today - timedelta(days=30)).strftime("%Y%m%d")
ftoday = today.strftime("%Y%m%d")
fd7  = (today - timedelta(days=7)).strftime("%Y%m%d")

r = check("get_focus_stats(heatmap, 30j)",
          lambda: get_focus_stats(from_date=fd30, to_date=ftoday))
if r is not None:
    assert_result("  retourne dict", r, isinstance(r, dict))
    print(f"    → clés: {list(r.keys())[:8]}")

# ── 10. get_focus_stats — heatmap 7j ─────────────────────────────────────────
r = check("get_focus_stats(heatmap, 7j)",
          lambda: get_focus_stats(from_date=fd7, to_date=ftoday))
if r is not None:
    assert_result("  retourne dict", r, isinstance(r, dict))

# ── 11. get_focus_stats — distribution ────────────────────────────────────────
r = check("get_focus_stats(distribution, 30j)",
          lambda: get_focus_stats(from_date=fd30, to_date=ftoday, stat_type="distribution"))
if r is not None:
    assert_result("  retourne dict", r, isinstance(r, dict))
    print(f"    → clés: {list(r.keys())[:8]}")

summary()
