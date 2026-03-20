"""
Script 1 / 8 — Utilitaires & Sync
Tests : ticktick_guide, check_v2_availability, build_recurrence_rule,
        build_reminder, full_sync, get_all_tasks, get_user_status,
        get_productivity_stats
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary

from tick_mcp.server import (
    ticktick_guide, check_v2_availability,
    build_recurrence_rule, build_reminder,
    full_sync, get_all_tasks, get_user_status, get_productivity_stats,
)

# ── 1. ticktick_guide ───────────────────────────────────────────────────────
_header("1/8 — Utilitaires & Sync")
r = check("ticktick_guide()", ticktick_guide)
assert_result("guide contient 'tool'", r, r and "tool" in str(r).lower())

# ── 2. check_v2_availability ─────────────────────────────────────────────────
r = check("check_v2_availability()", check_v2_availability, expect_key="v2_available")
assert_result("v2_available est bool", r, r and isinstance(r.get("v2_available"), bool))

# ── 3. build_recurrence_rule ─────────────────────────────────────────────────
cases = [
    ("daily",          dict(frequency="DAILY")),
    ("weekly Mon-Wed", dict(frequency="WEEKLY", by_day=["MO","WE"])),
    ("monthly 15th",   dict(frequency="MONTHLY", by_month_day=15)),
    ("every 2 weeks",  dict(frequency="WEEKLY", interval=2)),
    ("yearly mars",    dict(frequency="YEARLY", by_month=3, by_month_day=6)),
    ("daily 5x",       dict(frequency="DAILY", count=5)),
    ("until date",     dict(frequency="DAILY", until="20261231T000000Z")),
    ("invalid freq",   dict(frequency="HOURLY")),   # doit retourner erreur gracieuse
]
for name, kwargs in cases:
    r = check(f"build_recurrence_rule({name})", lambda k=kwargs: build_recurrence_rule(**k))
    if name != "invalid freq" and r:
        assert_result(f"  rrule contient FREQ", r,
                      r.get("rrule","").startswith("RRULE:FREQ="))

# ── 4. build_reminder ────────────────────────────────────────────────────────
reminder_cases = [
    ("at due time",    0),
    ("15min before",  15),
    ("30min before",  30),
    ("1h before",     60),
    ("1 day before", 1440),
    ("2 days before",2880),
    ("negative",      -5),  # edge case
]
for name, minutes in reminder_cases:
    r = check(f"build_reminder({name})", lambda m=minutes: build_reminder(m))
    if r and name != "negative":
        assert_result(f"  trigger est string", r, isinstance(r.get("trigger",""), str))

# ── 5. full_sync ──────────────────────────────────────────────────────────────
r = check("full_sync()", full_sync, expect_key="task_count")
if r:
    assert_result("  task_count >= 0",    r, r.get("task_count", -1) >= 0)
    assert_result("  projects est list",  r, isinstance(r.get("projects"), list))
    assert_result("  projects non vide",  r, len(r.get("projects", [])) > 0)
    assert_result("  tasks est list",     r, isinstance(r.get("tasks"), list))
    assert_result("  folders est list",   r, isinstance(r.get("folders"), list))
    assert_result("  tags est list",      r, isinstance(r.get("tags"), list))
    assert_result("  inboxId présent",    r, bool(r.get("inboxId")))
    show_sample("Extrait full_sync", {k: v for k,v in r.items() if k != "tasks"})

# ── 6. get_all_tasks ──────────────────────────────────────────────────────────
r = check("get_all_tasks()", get_all_tasks)
if r is not None:
    assert_result("  retourne une liste",   r, isinstance(r, list))
    if r:
        t = r[0]
        assert_result("  tâche a 'id'",     t, "id" in t)
        assert_result("  tâche a 'title'",  t, "title" in t)
        assert_result("  tâche a 'is_completed'", t, "is_completed" in t)
    print(f"    → {len(r)} tâches actives")

# ── 7. get_user_status ────────────────────────────────────────────────────────
r = check("get_user_status()", get_user_status, expect_key="userId")
if r:
    assert_result("  username présent",  r, bool(r.get("username")))
    assert_result("  inboxId présent",   r, bool(r.get("inboxId")))
    assert_result("  pro est bool",      r, isinstance(r.get("pro"), bool))

# ── 8. get_productivity_stats ─────────────────────────────────────────────────
r = check("get_productivity_stats()", get_productivity_stats)
if r:
    for k in ("score","level","totalCompleted","totalPomoCount"):
        assert_result(f"  {k} présent", r, k in r)

summary()
