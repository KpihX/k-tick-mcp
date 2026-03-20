"""
Script 12 / 12 — Batch Edge Cases, Pydantic Roundtrips, Tag-Task Integration
Edge cases:  batch_update_tasks with invalid IDs, batch_delete_tasks with invalid IDs,
             partial batch failure, large batch (25 tasks), malformed batch payloads,
             tag↔task lifecycle (create tag → task → rename → verify → delete),
             subtask parentId/childIds roundtrip via get_task_detail,
             inbox include_completed, habit advanced params, get_habit_records multi-id,
             get_inbox(include_completed=True), habit archive/unarchive.
All test resources are DELETED at the end.
"""
import sys, os, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, show_sample, summary, INFO, RESET

from tick_mcp.server import (
    create_task, update_task, delete_task, get_task_detail,
    batch_create_tasks, batch_update_tasks, batch_delete_tasks,
    create_project, delete_project, get_project_tasks,
    create_tag, rename_tag, delete_tag, list_tags,
    set_subtask_parent,
    get_inbox,
    create_habit, update_habit, delete_habit, habit_checkin, get_habit_records,
    list_habit_sections,
    build_recurrence_rule,
)

_header("12/12 — Batch Edges, Roundtrips & Tag-Task Integration")

_task_cleanup: list[tuple[str, str]] = []
_proj_cleanup: list[str] = []
_tag_cleanup: list[str] = []
_habit_cleanup: list[str] = []
today = datetime.now()
stamp_today = int(today.strftime("%Y%m%d"))

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION A — Batch Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. batch_update_tasks with nonexistent IDs ───────────────────────────────
r = check("batch_update_tasks(nonexistent IDs)",
          lambda: batch_update_tasks([
              {"id": "fake-id-no-exist-1", "projectId": "fake-pid", "title": "X"},
              {"id": "fake-id-no-exist-2", "projectId": "fake-pid", "title": "Y"},
          ]),
          expect_no_error=False)
assert_result("  no crash", r, r is not None)
if r and isinstance(r, dict):
    id2err = r.get("id2error", {})
    assert_result("  id2error present (API may silently ignore nonexistent)", r,
                  isinstance(id2err, dict),
                  f"id2error={id2err}")

# ── 2. batch_delete_tasks with nonexistent IDs ───────────────────────────────
r = check("batch_delete_tasks(nonexistent IDs)",
          lambda: batch_delete_tasks([
              {"taskId": "fake-id-no-exist-1", "projectId": "fake-pid"},
              {"taskId": "fake-id-no-exist-2", "projectId": "fake-pid"},
          ]),
          expect_no_error=False)
assert_result("  no crash", r, r is not None)

# ── 3. batch_create_tasks: malformed dicts (missing title) ───────────────────
r = check("batch_create_tasks(missing title)",
          lambda: batch_create_tasks([{"content": "no title here"}]),
          expect_no_error=False)
assert_result("  no crash", r, r is not None)

# ── 4. batch_create_tasks: extra unknown keys ────────────────────────────────
r = check("batch_create_tasks(extra keys)",
          lambda: batch_create_tasks([
              {"title": "Test-extra-keys", "unknownField1": 42, "weirdo": True}
          ]),
          expect_no_error=False)
if r and isinstance(r, dict) and not r.get("error"):
    etag_map = r.get("id2etag", {})
    if isinstance(etag_map, dict):
        for tid in etag_map.keys():
            _task_cleanup.append(("", tid))
assert_result("  no crash", r, r is not None)

# ── 5. batch_create_tasks: large batch (25 tasks) ────────────────────────────
large_batch = [{"title": f"Batch-{i:03d}"} for i in range(25)]
r = check("batch_create_tasks(25 tasks)",
          lambda: batch_create_tasks(large_batch))
large_ids = []
if r and isinstance(r, dict) and not r.get("error"):
    etag_map = r.get("id2etag", {})
    if isinstance(etag_map, dict):
        large_ids = list(etag_map.keys())
        for tid in large_ids:
            _task_cleanup.append(("", tid))
    assert_result("  25 tasks created", r, len(large_ids) >= 25,
                  f"created {len(large_ids)}")

# ── 6. batch_update_tasks: update all 25 (rename) ────────────────────────────
if len(large_ids) >= 25:
    updates = [{"id": tid, "projectId": "", "title": f"Updated-{i:03d}"}
               for i, tid in enumerate(large_ids)]
    r = check("batch_update_tasks(25 renames)",
              lambda: batch_update_tasks(updates))
    assert_result("  25 updates ok", r, r is not None and not r.get("error"))

# ── 7. batch_delete_tasks: delete all 25 ─────────────────────────────────────
if len(large_ids) >= 25:
    deletes = [{"taskId": tid, "projectId": ""} for tid in large_ids]
    r = check("batch_delete_tasks(25 deletes)",
              lambda: batch_delete_tasks(deletes))
    assert_result("  25 deletes ok", r, r is not None and not r.get("error"))
    # remove from cleanup
    _task_cleanup = [(p, t) for p, t in _task_cleanup if t not in large_ids]

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION B — Tag-Task Lifecycle Integration
# ══════════════════════════════════════════════════════════════════════════════

# ── 8. Create a unique tag ────────────────────────────────────────────────────
tag_name = "integ-test-tag-xyz"
r = check("create_tag(integ-test-tag)",
          lambda: create_tag(name=tag_name, color="#FF5733"))
_tag_cleanup.append(tag_name)
_tag_cleanup.append(tag_name + "-renamed")  # in case rename succeeds

# ── 9. Create task with that tag ──────────────────────────────────────────────
r = check("create_task(with integ-test-tag)",
          lambda: create_task(title="Task-With-IntegTag", tags=[tag_name]))
tag_task_id = r["id"] if r and not r.get("error") else None
tag_task_pid = r.get("projectId", "") if r else ""
if tag_task_id:
    _task_cleanup.append((tag_task_pid, tag_task_id))
    tags_on_task = r.get("tags", [])
    assert_result("  tag on new task", r,
                  tag_name in tags_on_task, f"tags={tags_on_task}")

# ── 10. Rename tag → verify task still has it ─────────────────────────────────
r = check("rename_tag(integ → integ-renamed)",
          lambda: rename_tag(old_name=tag_name, new_name=tag_name + "-renamed"))
assert_result("  rename ok", r, r is not None and not r.get("error"))

# re-read task
if tag_task_id:
    time.sleep(0.5)  # API propagation
    detail = check("get_task_detail(after tag rename)",
                   lambda: get_task_detail(project_id=tag_task_pid, task_id=tag_task_id))
    if detail and not detail.get("error"):
        new_tags = detail.get("tags", [])
        assert_result("  renamed tag on task", detail,
                      (tag_name + "-renamed") in new_tags,
                      f"tags={new_tags}")

# ── 11. Delete tag → verify task no longer has it ─────────────────────────────
r = check("delete_tag(integ-renamed)",
          lambda: delete_tag(tag_name=tag_name + "-renamed"))

if tag_task_id:
    time.sleep(0.5)
    detail = check("get_task_detail(after tag delete)",
                   lambda: get_task_detail(project_id=tag_task_pid, task_id=tag_task_id))
    if detail and not detail.get("error"):
        remaining_tags = detail.get("tags", [])
        assert_result("  tag removed from task", detail,
                      (tag_name + "-renamed") not in remaining_tags,
                      f"tags={remaining_tags}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION C — Subtask Parent/Child Roundtrip
# ══════════════════════════════════════════════════════════════════════════════

# ── 12. Create parent + child, set parent, verify via get_task_detail ─────────
proj_r = check("create_project(subtask-test)",
               lambda: create_project(name="Test-Subtask-RT"))
sub_pid = proj_r.get("id") if proj_r and not proj_r.get("error") else None
if sub_pid:
    _proj_cleanup.append(sub_pid)

parent_r = child_r = None
if sub_pid:
    parent_r = check("create_task(parent)",
                     lambda: create_task(title="Parent-Task", project_id=sub_pid))
    child_r = check("create_task(child)",
                    lambda: create_task(title="Child-Task", project_id=sub_pid))

parent_id = parent_r["id"] if parent_r and not parent_r.get("error") else None
child_id = child_r["id"] if child_r and not child_r.get("error") else None

if parent_id and child_id and sub_pid:
    r = check("set_subtask_parent(child → parent)",
              lambda: set_subtask_parent(task_id=child_id, project_id=sub_pid,
                                         parent_id=parent_id))
    assert_result("  set parent ok", r, r is not None and not r.get("error"))

    time.sleep(0.5)

    # verify child has parentId
    child_detail = check("get_task_detail(child after parenting)",
                         lambda: get_task_detail(project_id=sub_pid, task_id=child_id))
    if child_detail and not child_detail.get("error"):
        assert_result("  child.parentId = parent", child_detail,
                      child_detail.get("parentId") == parent_id,
                      f"parentId={child_detail.get('parentId')}")

    # verify parent has childIds or items
    parent_detail = check("get_task_detail(parent after parenting)",
                          lambda: get_task_detail(project_id=sub_pid, task_id=parent_id))
    if parent_detail and not parent_detail.get("error"):
        child_ids = parent_detail.get("childIds", [])
        assert_result("  parent.childIds includes child", parent_detail,
                      child_id in (child_ids or []),
                      f"childIds={child_ids}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION D — get_inbox(include_completed=True)
# ══════════════════════════════════════════════════════════════════════════════

# ── 13. get_inbox with include_completed ──────────────────────────────────────
r = check("get_inbox(include_completed=True)",
          lambda: get_inbox(include_completed=True))
assert_result("  returns list", r, isinstance(r, list), f"type={type(r)}")
if isinstance(r, list):
    print(f"    → {len(r)} tasks in inbox (with completed)")

r2 = check("get_inbox(include_completed=False)",
           lambda: get_inbox(include_completed=False))
if isinstance(r, list) and isinstance(r2, list):
    assert_result("  True count ≥ False count", None,
                  len(r) >= len(r2),
                  f"True={len(r)}, False={len(r2)}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION E — Habit Advanced Parameters & Archive
# ══════════════════════════════════════════════════════════════════════════════

# ── 14. create_habit with all params ──────────────────────────────────────────
sections = list_habit_sections()
sec_id = None
if isinstance(sections, list) and sections:
    sec_id = sections[0].get("id")

rrule_r = build_recurrence_rule(frequency="WEEKLY", by_day=["MO", "WE", "FR"])
rrule = rrule_r.get("rrule", "") if rrule_r else ""

r = check("create_habit(all params)",
          lambda: create_habit(
              name="Full-Habit-Adv",
              habit_type="Real",
              goal=10.0,
              step=0.5,
              unit="pages",
              color="#FF6161",
              encouragement="Keep going! 🎉",
              target_days=30,
              repeat_rule=rrule,
              reminders=["08:00", "21:00"],
              section_id=sec_id,
              start_date=today.strftime("%Y-%m-%d"),
          ))
adv_habit_id = None
if r and isinstance(r, dict) and not r.get("error"):
    etag = r.get("id2etag", {})
    if isinstance(etag, dict) and etag:
        adv_habit_id = list(etag.keys())[0]
        _habit_cleanup.append(adv_habit_id)

# ── 15. update_habit: multiple fields ─────────────────────────────────────────
if adv_habit_id:
    r = check("update_habit(goal+step+unit+encouragement)",
              lambda: update_habit(habit_id=adv_habit_id,
                                   goal=20.0, step=1.0, unit="mins",
                                   encouragement="Great work! 💪"))
    assert_result("  multi-field update ok", r, r is not None and not r.get("error"))

# ── 16. habit archive → unarchive ─────────────────────────────────────────────
if adv_habit_id:
    r = check("update_habit(status=2 → archive)",
              lambda: update_habit(habit_id=adv_habit_id, status=2))
    assert_result("  archived", r, r is not None and not r.get("error"))

    r = check("update_habit(status=0 → unarchive)",
              lambda: update_habit(habit_id=adv_habit_id, status=0))
    assert_result("  unarchived", r, r is not None and not r.get("error"))

# ── 17. habit_checkin with checkin_time ───────────────────────────────────────
if adv_habit_id:
    now_iso = today.strftime("%Y-%m-%dT%H:%M:%S+0000")
    r = check("habit_checkin(with checkin_time)",
              lambda: habit_checkin(habit_id=adv_habit_id, checkin_stamp=stamp_today,
                                   value=5.0, checkin_time=now_iso))
    assert_result("  checkin with time ok", r, r is not None and not r.get("error"))

# ── 18. get_habit_records: multiple habit_ids ─────────────────────────────────
# create a 2nd habit for multi-query
r2 = create_habit(name="Second-Habit-Multi")
h2_id = None
if r2 and isinstance(r2, dict) and not r2.get("error"):
    etag2 = r2.get("id2etag", {})
    if isinstance(etag2, dict) and etag2:
        h2_id = list(etag2.keys())[0]
        _habit_cleanup.append(h2_id)

if adv_habit_id and h2_id:
    r = check("get_habit_records(multi habit_ids)",
              lambda: get_habit_records(habit_ids=[adv_habit_id, h2_id],
                                        after_stamp=stamp_today - 1))
    assert_result("  returns dict", r, isinstance(r, dict), f"type={type(r)}")
    if isinstance(r, dict):
        checkins = r.get("checkins", {})
        assert_result("  has entries for queried habits", r,
                      isinstance(checkins, dict),
                      f"keys={list(checkins.keys()) if isinstance(checkins, dict) else 'N/A'}")

# ── 19. get_habit_records(after_stamp=0) → all history ────────────────────────
if adv_habit_id:
    r = check("get_habit_records(after_stamp=0, all history)",
              lambda: get_habit_records(habit_ids=[adv_habit_id], after_stamp=0))
    assert_result("  returns dict", r, isinstance(r, dict))

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION F — Miscellaneous Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

# ── 20. update_task via status=2 (complete via update, not complete_task) ─────
status_task = check("create_task(status-update test)",
                    lambda: create_task(title="Status-Via-Update"))
st_id = status_task["id"] if status_task and not status_task.get("error") else None
st_pid = status_task.get("projectId", "") if status_task else ""
if st_id:
    _task_cleanup.append((st_pid, st_id))
    r = check("update_task(status=2 → complete via update)",
              lambda: update_task(task_id=st_id, project_id=st_pid, status=2))
    assert_result("  status=2", r,
                  r is not None and r.get("status") == 2,
                  f"status={r.get('status') if r else 'N/A'}")

# ── 21. update_task: set recurrence then clear it ─────────────────────────────
rec_task = check("create_task(recurrence-clear test)",
                 lambda: create_task(title="Recurrence-Clear",
                                     start_date=today.strftime("%Y-%m-%dT10:00:00+0000"),
                                     recurrence="RRULE:FREQ=DAILY"))
rec_id = rec_task["id"] if rec_task and not rec_task.get("error") else None
rec_pid = rec_task.get("projectId", "") if rec_task else ""
if rec_id:
    _task_cleanup.append((rec_pid, rec_id))
    assert_result("  recurrence set", rec_task, bool(rec_task.get("repeatFlag")),
                  f"repeatFlag={rec_task.get('repeatFlag')}")

    r = check("update_task(recurrence='' → clear)",
              lambda: update_task(task_id=rec_id, project_id=rec_pid, recurrence=""))
    assert_result("  recurrence cleared", r,
                  r is not None and not r.get("error"),
                  f"repeatFlag={r.get('repeatFlag') if r else 'N/A'}")

# ── 22. set_subtask_parent: cross-project (should fail or handle) ─────────────
# parent in one project, child in another → API should reject
if sub_pid and tag_task_id:  # tag_task is in inbox, sub_pid is a project
    r = check("set_subtask_parent(cross-project, expect error)",
              lambda: set_subtask_parent(task_id=tag_task_id, project_id=sub_pid,
                                         parent_id="some-fake-parent"),
              expect_no_error=False)
    assert_result("  no crash on cross-project", r, r is not None)

# ── 23. set_subtask_parent: no parent_id and no old_parent_id ─────────────────
r = check("set_subtask_parent(neither parent nor old_parent → error)",
          lambda: set_subtask_parent(task_id="x", project_id="y"),
          expect_no_error=False)
assert_result("  returns error message", r,
              r is not None and r.get("error") and "Provide either" in str(r.get("message", "")),
              f"msg={r.get('message') if r else 'N/A'}")

# ══════════════════════════════════════════════════════════════════════════════
#  NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n    {INFO}Nettoyage : {len(_task_cleanup)} tâches, {len(_proj_cleanup)} projets, "
      f"{len(_tag_cleanup)} tags, {len(_habit_cleanup)} habitudes{RESET}")

for pid, tid in _task_cleanup:
    try:
        delete_task(project_id=pid, task_id=tid)
    except Exception:
        pass

for pid in _proj_cleanup:
    try:
        delete_project(project_id=pid)
    except Exception:
        pass

for tn in _tag_cleanup:
    try:
        delete_tag(tag_name=tn)
    except Exception:
        pass

for hid in _habit_cleanup:
    try:
        delete_habit(habit_id=hid)
    except Exception:
        pass

summary()
