"""
Script 7 / 8 — Habitudes
Tests : list_habits, list_habit_sections, create_habit, update_habit,
        delete_habit, habit_checkin, get_habit_records
Toutes les habitudes créées sont SUPPRIMÉES à la fin.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET
from datetime import date, timedelta

from k_tick_mcp.server import (
    list_habits, list_habit_sections, create_habit,
    update_habit, delete_habit, habit_checkin, get_habit_records,
)

_header("7/8 — Habitudes")

created_habit_ids: list[str] = []
today_str = date.today().strftime("%Y%m%d")
yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

# ── 1. list_habits ────────────────────────────────────────────────────────────
r = check("list_habits()", list_habits)
assert_result("  retourne liste", r, r is not None and isinstance(r, list))
existing_habits = r or []
if existing_habits:
    h0 = existing_habits[0]
    for k in ("id","name","type"):
        assert_result(f"  habit a '{k}'", h0, k in h0)
    print(f"    → {len(existing_habits)} habitude(s) existante(s)")

# ── 2. list_habit_sections ────────────────────────────────────────────────────
r = check("list_habit_sections()", list_habit_sections)
assert_result("  retourne liste", r, r is not None and isinstance(r, list))
section_id = None
if r:
    print(f"    → {len(r)} section(s): {[s.get('name','?') for s in r[:5]]}")
    section_id = r[0].get("id") if r else None

# ── 3. create_habit — Boolean ─────────────────────────────────────────────────
r = check("create_habit(Boolean)",
          lambda: create_habit(
              name="[TEST] Habitude Bool",
              habit_type="Boolean",
              repeat_rule="RRULE:FREQ=DAILY",
              reminders=["09:00"],
          ))
if r and isinstance(r, dict) and not r.get("error"):
    hab_ids = list((r.get("id2etag") or {}).keys())
    if hab_ids:
        created_habit_ids.append(hab_ids[0])
        assert_result("  id présent", r, bool(hab_ids[0]))

# ── 4. create_habit — Real (mesurable avec goal) ──────────────────────────────
r = check("create_habit(Real + goal)",
          lambda: create_habit(
              name="[TEST] Habitude Real",
              habit_type="Real",
              repeat_rule="RRULE:FREQ=DAILY",
              goal=8.0,
              unit="verres",
              color="#4CA1FF",
          ))
if r and isinstance(r, dict) and not r.get("error"):
    hab_ids = list((r.get("id2etag") or {}).keys())
    if hab_ids:
        created_habit_ids.append(hab_ids[0])

# ── 5. create_habit — dans une section ───────────────────────────────────────
if section_id:
    r = check("create_habit(dans section)",
              lambda: create_habit(
                  name="[TEST] Habitude Sectionnée",
                  habit_type="Boolean",
                  repeat_rule="RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR",
                  section_id=section_id,
              ))
    if r and isinstance(r, dict) and not r.get("error"):
        hab_ids = list((r.get("id2etag") or {}).keys())
        if hab_ids:
            created_habit_ids.append(hab_ids[0])
else:
    check("create_habit(dans section)", lambda: None, skip_reason="pas de section disponible")

# ── 6. create_habit — nom vide (edge case) ────────────────────────────────────
r = check("create_habit(nom vide)", lambda: create_habit(name="", habit_type="Boolean",
          repeat_rule="RRULE:FREQ=DAILY"), expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 7. update_habit ───────────────────────────────────────────────────────────
if created_habit_ids:
    hid = created_habit_ids[0]
    r = check("update_habit(name + color)",
              lambda: update_habit(habit_id=hid, name="[TEST] Habitude Bool MODIFIÉE",
                                   color="#35D870"))
    assert_result("  pas de crash", r, r is not None)

# ── 8. update_habit — id invalide ─────────────────────────────────────────────
r = check("update_habit(invalid id)", lambda: update_habit(habit_id="badbadid"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 9. habit_checkin — Boolean (done) ─────────────────────────────────────────
if created_habit_ids:
    hid = created_habit_ids[0]
    r = check(f"habit_checkin(Boolean, today, done)",
              lambda: habit_checkin(habit_id=hid, checkin_stamp=int(today_str), value=1))
    assert_result("  pas de crash", r, r is not None)

    # annuler le check-in
    r2 = check(f"habit_checkin(Boolean, today, undo)",
               lambda: habit_checkin(habit_id=hid, checkin_stamp=int(today_str), value=0, status=0))
    assert_result("  pas de crash", r2, r2 is not None)

    # hier
    r3 = check(f"habit_checkin(Boolean, yesterday)",
               lambda: habit_checkin(habit_id=hid, checkin_stamp=int(yesterday_str), value=1))
    assert_result("  pas de crash", r3, r3 is not None)

# ── 10. habit_checkin — Real (avec valeur partielle) ──────────────────────────
if len(created_habit_ids) >= 2:
    hid = created_habit_ids[1]
    r = check("habit_checkin(Real, valeur=5.5)",
              lambda: habit_checkin(habit_id=hid, checkin_stamp=int(today_str), value=5.5))
    assert_result("  pas de crash", r, r is not None)

# ── 11. habit_checkin — id invalide ───────────────────────────────────────────
r = check("habit_checkin(invalid id)", lambda: habit_checkin(habit_id="badid", checkin_stamp=int(today_str), value=1),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

# ── 12. get_habit_records ─────────────────────────────────────────────────────
if created_habit_ids:
    hid = created_habit_ids[0]
    # période courte
    stamp_7d = int((date.today() - timedelta(days=7)).strftime("%Y%m%d"))
    r = check("get_habit_records(7 jours)",
              lambda: get_habit_records(habit_ids=[hid], after_stamp=stamp_7d))
    assert_result("  retourne liste ou dict", r, r is not None)

    # id invalide
    r2 = check("get_habit_records(invalid id)",
               lambda: get_habit_records(habit_ids=["badid"], after_stamp=int(today_str)),
               expect_no_error=False)
    assert_result("  pas de crash", r2, r2 is not None)

# ── 13. get_habit_records — existants ─────────────────────────────────────────
if existing_habits:
    hid = existing_habits[0]["id"]
    stamp_30d = int((date.today() - timedelta(days=30)).strftime("%Y%m%d"))
    r = check(f"get_habit_records(habitude existante, 30j)",
              lambda: get_habit_records(habit_ids=[hid], after_stamp=stamp_30d))
    assert_result("  pas de crash", r, r is not None)

# ── NETTOYAGE ─────────────────────────────────────────────────────────────────
print(f"\n    {INFO} Nettoyage {len(created_habit_ids)} habitudes...{RESET}")
for hid in created_habit_ids:
    r = check(f"delete_habit({hid[:8]}...)", lambda h=hid: delete_habit(habit_id=h))
    assert_result("  pas de crash", r, r is not None)

# ── 14. delete_habit — id invalide ────────────────────────────────────────────
r = check("delete_habit(invalid id)", lambda: delete_habit(habit_id="baaadid"),
          expect_no_error=False)
assert_result("  pas de crash", r, r is not None)

summary()
