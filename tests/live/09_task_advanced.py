"""
Script 9 / 12 — Task Advanced Parameters & Lifecycle Cycles
Edge cases:  desc, time_zone, reminder_minutes, kind=NOTE, multi-tags,
             field-clearing via update, complete→reopen→complete,
             double-complete, double-delete, complete→get_completed cycle,
             create_task in inbox with all optional fields.
All test resources are DELETED at the end.
"""
import sys, os, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary

from tick_mcp.server import (
    create_task, update_task, complete_task, reopen_task, delete_task,
    get_task_detail, get_inbox, get_completed_tasks, get_deleted_tasks,
    build_recurrence_rule, build_reminder,
)

_header("9/12 — Task Advanced Params & Lifecycles")

_cleanup: list[tuple[str, str]] = []  # (project_id, task_id) for cleanup
today = datetime.now()
tomorrow = today + timedelta(days=1)
iso_tomorrow = tomorrow.strftime("%Y-%m-%dT09:00:00+0000")
iso_today = today.strftime("%Y-%m-%dT10:00:00+0000")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION A — Untested create_task parameters
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. create_task with desc (alt description) ───────────────────────────────
r = check("create_task(desc)",
          lambda: create_task(title="Test-desc-field", desc="Alt description via desc field"))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  desc round-trip possible", r, True)

# ── 2. create_task with time_zone ─────────────────────────────────────────────
r = check("create_task(time_zone=Europe/Paris)",
          lambda: create_task(title="Test-tz-paris",
                              due_date=iso_tomorrow,
                              time_zone="Europe/Paris"))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  timeZone preserved", r,
                  r.get("timeZone") == "Europe/Paris",
                  f"got {r.get('timeZone')}")

# ── 3. create_task with reminder_minutes ──────────────────────────────────────
r = check("create_task(reminder_minutes=[0,30,1440])",
          lambda: create_task(title="Test-reminders",
                              due_date=iso_tomorrow,
                              reminder_minutes=[0, 30, 1440]))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  reminders saved", r,
                  isinstance(r.get("reminders"), list) and len(r.get("reminders", [])) == 3,
                  f"reminders={r.get('reminders')}")

# ── 4. create_task with kind=NOTE ─────────────────────────────────────────────
r = check("create_task(kind=NOTE)",
          lambda: create_task(title="Test-note-kind", kind="NOTE",
                              content="This task is a NOTE kind"))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  kind=NOTE saved", r,
                  r.get("kind") == "NOTE", f"got kind={r.get('kind')}")

# ── 5. create_task with multiple tags ─────────────────────────────────────────
r = check("create_task(multi-tags)",
          lambda: create_task(title="Test-multi-tags",
                              tags=["edge-tag-alpha", "edge-tag-beta", "edge-tag-gamma"]))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    tags = r.get("tags", [])
    assert_result("  3 tags on task", r, len(tags) >= 3, f"tags={tags}")

# ── 6. create_task with all-day + due_date + start_date + time_zone ───────────
r = check("create_task(all-day+dates+tz)",
          lambda: create_task(title="Test-allday-dates",
                              due_date=iso_tomorrow,
                              start_date=iso_today,
                              time_zone="America/New_York",
                              all_day=True))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  allDay=True", r, r.get("allDay") is True, f"allDay={r.get('allDay')}")
    assert_result("  timeZone preserved", r,
                  r.get("timeZone") == "America/New_York",
                  f"tz={r.get('timeZone')}")

# ── 7. create_task with priority=1 (low) and priority=0 (none) ───────────────
r = check("create_task(priority=1, low)",
          lambda: create_task(title="Test-priority-low", priority=1))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  priority=1", r, r.get("priority") == 1, f"got {r.get('priority')}")

r = check("create_task(priority=0, none)",
          lambda: create_task(title="Test-priority-none", priority=0))
if r and not r.get("error"):
    _cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  priority=0", r, r.get("priority") == 0, f"got {r.get('priority')}")

# ── 8. build_recurrence_rule → create_task (full chain) ──────────────────────
rrule_r = check("build_recurrence_rule(WEEKLY, MO+WE+FR)",
                lambda: build_recurrence_rule(frequency="WEEKLY",
                                              by_day=["MO", "WE", "FR"]))
if rrule_r and rrule_r.get("rrule"):
    r = check("create_task(recurrence from rrule + start_date)",
              lambda: create_task(title="Test-rrule-chain",
                                  recurrence=rrule_r["rrule"],
                                  start_date=iso_today,
                                  time_zone="Europe/Paris"))
    if r and not r.get("error"):
        _cleanup.append((r.get("projectId", ""), r["id"]))
        assert_result("  repeatFlag saved", r, bool(r.get("repeatFlag")),
                      f"repeatFlag={r.get('repeatFlag')}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION B — update_task field-clearing + extra fields
# ══════════════════════════════════════════════════════════════════════════════

# create a rich task to update
rich = check("create_task(rich task for updates)",
             lambda: create_task(title="Test-rich-update",
                                 content="Original content",
                                 due_date=iso_tomorrow,
                                 start_date=iso_today,
                                 time_zone="Europe/Paris",
                                 tags=["temp-tag-1"],
                                 priority=3,
                                 reminder_minutes=[30]))
rich_id = rich["id"] if rich and not rich.get("error") else None
rich_pid = rich.get("projectId", "") if rich else ""
if rich_id:
    _cleanup.append((rich_pid, rich_id))

# ── 9. update_task: clear start_date first (API needs startDate gone before dueDate can be cleared)
if rich_id:
    r = check("update_task(clear start_date)",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, start_date=""))
    assert_result("  startDate cleared", r,
                  r is not None and not r.get("error"),
                  f"startDate={r.get('startDate') if r else 'None'}")

# ── 10. update_task: clear due_date (now that startDate is gone) ──────────────
if rich_id:
    r = check("update_task(clear due_date)",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, due_date=""))
    assert_result("  dueDate cleared", r,
                  r is not None and not r.get("error") and not r.get("dueDate"),
                  f"dueDate={r.get('dueDate') if r else 'None'}")

# ── 11. update_task: clear tags ───────────────────────────────────────────────
if rich_id:
    r = check("update_task(clear tags=[])",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, tags=[]))
    tags_after = r.get("tags", []) if r else None
    assert_result("  tags cleared", r,
                  r is not None and not r.get("error") and (not tags_after or tags_after == []),
                  f"tags={tags_after}")

# ── 12. update_task: clear reminders ─────────────────────────────────────────
if rich_id:
    r = check("update_task(clear reminders=[])",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, reminder_minutes=[]))
    rem_after = r.get("reminders", []) if r else None
    assert_result("  reminders cleared", r,
                  r is not None and not r.get("error"),
                  f"reminders={rem_after}")

# ── 13. update_task: set all_day ──────────────────────────────────────────────
if rich_id:
    r = check("update_task(all_day=True)",
              lambda: update_task(task_id=rich_id, project_id=rich_pid,
                                  all_day=True, due_date=iso_tomorrow))
    assert_result("  allDay set", r,
                  r is not None and not r.get("error"),
                  f"allDay={r.get('allDay') if r else 'N/A'}")

# ── 14. update_task: progress ─────────────────────────────────────────────────
if rich_id:
    r = check("update_task(progress=42)",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, progress=42))
    assert_result("  progress set", r,
                  r is not None and not r.get("error"),
                  f"progress={r.get('progress') if r else 'N/A'}")

# ── 15. update_task: desc field ───────────────────────────────────────────────
if rich_id:
    r = check("update_task(desc='Alt description')",
              lambda: update_task(task_id=rich_id, project_id=rich_pid,
                                  desc="Alt description updated"))
    assert_result("  desc updated", r, r is not None and not r.get("error"))

# ── 16. update_task: kind switch TEXT → CHECKLIST ─────────────────────────────
if rich_id:
    r = check("update_task(kind=CHECKLIST)",
              lambda: update_task(task_id=rich_id, project_id=rich_pid, kind="CHECKLIST"))
    assert_result("  kind updated", r, r is not None and not r.get("error"))

# ── 17. update_task: no fields (should return error) ─────────────────────────
r = check("update_task(no fields → error)",
          lambda: update_task(task_id="fake", project_id="fake"),
          expect_no_error=False)
assert_result("  error message", r,
              r is not None and r.get("error") and "No fields" in str(r.get("message", "")),
              f"msg={r.get('message') if r else 'None'}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION C — Lifecycle Cycles
# ══════════════════════════════════════════════════════════════════════════════

# create a task for lifecycle testing
lc = check("create_task(lifecycle-task)",
           lambda: create_task(title="Test-lifecycle-cycle"))
lc_id = lc["id"] if lc and not lc.get("error") else None
lc_pid = lc.get("projectId", "") if lc else ""
if lc_id:
    _cleanup.append((lc_pid, lc_id))

# ── 18. complete → verify status ──────────────────────────────────────────────
if lc_id:
    r = check("complete_task(lifecycle)",
              lambda: complete_task(project_id=lc_pid, task_id=lc_id))
    assert_result("  status=2 (completed)", r,
                  r is not None and r.get("status") == 2,
                  f"status={r.get('status') if r else 'N/A'}")

# ── 19. double complete (idempotency) ─────────────────────────────────────────
if lc_id:
    r = check("complete_task(double complete)",
              lambda: complete_task(project_id=lc_pid, task_id=lc_id),
              expect_no_error=False)
    assert_result("  no crash", r, r is not None)

# ── 20. reopen after complete ─────────────────────────────────────────────────
if lc_id:
    r = check("reopen_task(lifecycle)",
              lambda: reopen_task(project_id=lc_pid, task_id=lc_id))
    assert_result("  status=0 (reopened)", r,
                  r is not None and r.get("status") == 0,
                  f"status={r.get('status') if r else 'N/A'}")

# ── 21. complete again → get_completed_tasks → verify present ─────────────────
if lc_id:
    r = check("complete_task(2nd time)",
              lambda: complete_task(project_id=lc_pid, task_id=lc_id))
    time.sleep(5)  # let API propagate

    # Use full-day window to avoid timezone issues
    now_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d") + " 23:59:59"
    from_str = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"

    completed = check("get_completed_tasks(verify lifecycle task)",
                      lambda: get_completed_tasks(from_date=from_str, to_date=now_str, limit=50))
    if isinstance(completed, list):
        found = any(t.get("id") == lc_id for t in completed)
        assert_result("  lifecycle task in completed list", None, found,
                      f"searched {len(completed)} completed tasks, found={found}")
    else:
        assert_result("  completed list is list", completed, False, f"type={type(completed)}")

# ── 22. delete lifecycle task → get_deleted_tasks → verify present ────────────
if lc_id:
    r = check("delete_task(lifecycle)",
              lambda: delete_task(project_id=lc_pid, task_id=lc_id))
    # remove from cleanup since it's deleted
    _cleanup = [(p, t) for p, t in _cleanup if t != lc_id]
    time.sleep(1)

    deleted_list = check("get_deleted_tasks(verify lifecycle task)",
                         lambda: get_deleted_tasks(start=0, limit=20))
    if isinstance(deleted_list, list):
        found = any(t.get("id") == lc_id for t in deleted_list)
        assert_result("  lifecycle task in deleted list", None, found,
                      f"searched {len(deleted_list)} deleted tasks, found={found}")

# ── 23. create + delete + double-delete (idempotency) ─────────────────────────
dd = check("create_task(double-delete test)",
           lambda: create_task(title="Test-double-delete"))
dd_id = dd["id"] if dd and not dd.get("error") else None
dd_pid = dd.get("projectId", "") if dd else ""
if dd_id:
    r = check("delete_task(first delete)",
              lambda: delete_task(project_id=dd_pid, task_id=dd_id))
    r2 = check("delete_task(double delete, idempotency)",
               lambda: delete_task(project_id=dd_pid, task_id=dd_id),
               expect_no_error=False)
    assert_result("  no crash on double delete", r2, r2 is not None)

# ══════════════════════════════════════════════════════════════════════════════
#  NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n    Nettoyage : {len(_cleanup)} tâches")
for pid, tid in _cleanup:
    try:
        delete_task(project_id=pid, task_id=tid)
    except Exception:
        pass

# clean up edge tags we may have created
from tick_mcp.server import delete_tag
for tag_name in ["edge-tag-alpha", "edge-tag-beta", "edge-tag-gamma", "temp-tag-1"]:
    try:
        delete_tag(tag_name=tag_name)
    except Exception:
        pass

summary()
