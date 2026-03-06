"""
Script 11 / 12 — Unicode, Special Characters, Long Strings, Date Edge Cases
Edge cases:  emoji/CJK/arabic in titles & content,  <script> XSS probe,
             markdown content, very long title/content, empty-string title,
             invalid date formats, past due_date, priority edge values (2,4,-1,99),
             date with various TZ offsets, date without time.
All test resources are DELETED at the end.
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from _helper import _header, check, assert_result, summary

from k_tick_mcp.server import (
    create_task, update_task, delete_task, get_task_detail,
    create_project, delete_project,
    create_tag, delete_tag,
    create_habit, delete_habit,
)

_header("11/12 — Unicode, Special Chars, Long Strings & Date Edges")

_task_cleanup: list[tuple[str, str]] = []
_proj_cleanup: list[str] = []
_tag_cleanup: list[str] = []
_habit_cleanup: list[str] = []

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION A — Unicode & Special Characters
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Emoji in title ─────────────────────────────────────────────────────────
r = check("create_task(emoji title 🎯🔥🚀)",
          lambda: create_task(title="Test 🎯 emoji 🔥 rocket 🚀"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  emoji preserved in title", r,
                  "🎯" in r.get("title", ""), f"title={r.get('title')}")

# ── 2. CJK characters ────────────────────────────────────────────────────────
r = check("create_task(CJK 日本語タスク)",
          lambda: create_task(title="日本語テスト 中文测试 한국어시험"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  CJK preserved", r,
                  "日本語" in r.get("title", ""), f"title={r.get('title')}")

# ── 3. Arabic + RTL ──────────────────────────────────────────────────────────
r = check("create_task(Arabic مهمة اختبار)",
          lambda: create_task(title="اختبار المهمة العربية"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  arabic preserved", r,
                  "اختبار" in r.get("title", ""), f"title={r.get('title')}")

# ── 4. HTML/XSS probe in content ─────────────────────────────────────────────
r = check("create_task(XSS <script>)",
          lambda: create_task(title="Test-XSS-Content",
                              content='<script>alert("xss")</script><img onerror=alert(1) src=x>'))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    # just check it stores something, API may sanitize
    assert_result("  content stored", r, r.get("content") is not None)

# ── 5. Markdown in content ───────────────────────────────────────────────────
md = "# Heading\n\n**Bold** and *italic* and `code`\n\n- item 1\n- item 2\n\n[link](https://example.com)"
r = check("create_task(markdown content)",
          lambda: create_task(title="Test-Markdown", content=md))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  markdown stored", r, len(r.get("content", "")) > 10)

# ── 6. Special chars: & < > " ' \ / \n \t ────────────────────────────────────
special = 'Test & "quotes" \'single\' <angle> /slash\\ tab\there new\nline'
r = check("create_task(special chars)",
          lambda: create_task(title=special))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  no crash, title stored", r, len(r.get("title", "")) > 5)

# ── 7. Unicode project name ──────────────────────────────────────────────────
r = check("create_project(emoji 📋 Projet)",
          lambda: create_project(name="📋 Projet Unicode éàü Ñ"))
if r and not r.get("error"):
    _proj_cleanup.append(r["id"])
    assert_result("  unicode project name", r,
                  "📋" in r.get("name", ""), f"name={r.get('name')}")

# ── 8. Unicode tag name ──────────────────────────────────────────────────────
r = check("create_tag(emoji 🏷️ étiquette)",
          lambda: create_tag(name="🏷️-étiquette-テスト"))
if r and not r.get("error"):
    _tag_cleanup.append("🏷️-étiquette-テスト")
    assert_result("  unicode tag ok", r, True)

# ── 9. Unicode habit name ────────────────────────────────────────────────────
r = check("create_habit(emoji 🧘 Méditation)",
          lambda: create_habit(name="🧘 Méditation クイック"))
if r and not r.get("error"):
    etag = r.get("id2etag", {})
    if isinstance(etag, dict) and etag:
        hid = list(etag.keys())[0]
        _habit_cleanup.append(hid)
    assert_result("  unicode habit ok", r, True)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION B — String Length Boundaries
# ══════════════════════════════════════════════════════════════════════════════

# ── 10. Very long title (500 chars) ──────────────────────────────────────────
long_title = "L" * 500
r = check("create_task(500-char title)",
          lambda: create_task(title=long_title))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  long title accepted", r, len(r.get("title", "")) >= 100)

# ── 11. Very long content (5000 chars) ───────────────────────────────────────
long_content = "Paragraph. " * 500  # ~5500 chars
r = check("create_task(5000-char content)",
          lambda: create_task(title="Test-Long-Content", content=long_content))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  long content accepted", r, len(r.get("content", "")) >= 1000)

# ── 12. Empty title ──────────────────────────────────────────────────────────
r = check("create_task(empty title)", lambda: create_task(title=""),
          expect_no_error=False)
assert_result("  no crash", r, r is not None)

# ── 13. Whitespace-only title ─────────────────────────────────────────────────
r = check("create_task(whitespace title)", lambda: create_task(title="   \t  "),
          expect_no_error=False)
if r and not r.get("error") and r.get("id"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
assert_result("  no crash", r, r is not None)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION C — Date Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

# ── 14. Due date in the past ─────────────────────────────────────────────────
r = check("create_task(past due_date 2020-01-01)",
          lambda: create_task(title="Test-Past-Due",
                              due_date="2020-01-01T09:00:00+0000"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  past date accepted", r, r.get("dueDate") is not None)

# ── 15. Due date far future ──────────────────────────────────────────────────
r = check("create_task(far future 2099-12-31)",
          lambda: create_task(title="Test-Far-Future",
                              due_date="2099-12-31T23:59:00+0000"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  far future accepted", r, r.get("dueDate") is not None)

# ── 16. Date with +0200 offset ───────────────────────────────────────────────
r = check("create_task(due_date +0200)",
          lambda: create_task(title="Test-TZ-Offset",
                              due_date="2026-06-15T14:00:00+0200",
                              time_zone="Europe/Paris"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  +0200 offset accepted", r, r.get("dueDate") is not None)

# ── 17. Date with Z suffix ───────────────────────────────────────────────────
r = check("create_task(due_date Z suffix)",
          lambda: create_task(title="Test-Z-Suffix",
                              due_date="2026-06-15T14:00:00Z"))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  Z suffix accepted (may drop date)", r,
                  r is not None and not r.get("error"),
                  f"dueDate={r.get('dueDate')}")

# ── 18. Invalid date string ──────────────────────────────────────────────────
r = check("create_task(invalid date 'not-a-date')",
          lambda: create_task(title="Test-Invalid-Date",
                              due_date="not-a-date-at-all"),
          expect_no_error=False)
if r and not r.get("error") and r.get("id"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
assert_result("  no crash", r, r is not None)

# ── 19. Date-only (no time component) ────────────────────────────────────────
r = check("create_task(date-only '2026-07-01')",
          lambda: create_task(title="Test-Date-Only",
                              due_date="2026-07-01", all_day=True))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  date-only accepted (may drop date)", r,
                  r is not None and not r.get("error"),
                  f"dueDate={r.get('dueDate')}")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION D — Priority Edge Values
# ══════════════════════════════════════════════════════════════════════════════

# ── 20. priority=2 (non-standard) ────────────────────────────────────────────
r = check("create_task(priority=2, non-standard)",
          lambda: create_task(title="Test-Priority-2", priority=2))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  priority stored", r, r.get("priority") is not None,
                  f"priority={r.get('priority')}")

# ── 21. priority=4 (non-standard) ────────────────────────────────────────────
r = check("create_task(priority=4, non-standard)",
          lambda: create_task(title="Test-Priority-4", priority=4))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  priority stored", r, r.get("priority") is not None,
                  f"priority={r.get('priority')}")

# ── 22. priority=5 (max = high) ──────────────────────────────────────────────
r = check("create_task(priority=5, high)",
          lambda: create_task(title="Test-Priority-5", priority=5))
if r and not r.get("error"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
    assert_result("  priority=5", r, r.get("priority") == 5)
    assert_result("  label=high", r,
                  r.get("priority_label") == "high",
                  f"label={r.get('priority_label')}")

# ── 23. priority=-1 (out of range) ───────────────────────────────────────────
r = check("create_task(priority=-1, invalid)",
          lambda: create_task(title="Test-Priority-Neg", priority=-1),
          expect_no_error=False)
if r and not r.get("error") and r.get("id"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
assert_result("  no crash", r, r is not None)

# ── 24. priority=99 (way out of range) ───────────────────────────────────────
r = check("create_task(priority=99, invalid)",
          lambda: create_task(title="Test-Priority-99", priority=99),
          expect_no_error=False)
if r and not r.get("error") and r.get("id"):
    _task_cleanup.append((r.get("projectId", ""), r["id"]))
assert_result("  no crash", r, r is not None)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION E — get_task_detail roundtrip verification
# ══════════════════════════════════════════════════════════════════════════════

# create a task with many fields, then re-read and verify all fields
r = check("create_task(roundtrip rich task)",
          lambda: create_task(
              title="Roundtrip-Test 🎯",
              content="Rich **markdown** content\n- item1\n- item2",
              desc="Alt desc field",
              priority=3,
              due_date="2026-08-01T10:00:00+0000",
              start_date="2026-07-28T08:00:00+0000",
              time_zone="Europe/Paris",
              tags=["roundtrip-tag"],
              all_day=False,
              reminder_minutes=[0, 60],
              checklist_items=["Sous-tâche A", "Sous-tâche B", "Sous-tâche C"],
          ))
rt_id = r["id"] if r and not r.get("error") else None
rt_pid = r.get("projectId", "") if r else ""
if rt_id:
    _task_cleanup.append((rt_pid, rt_id))
    _tag_cleanup.append("roundtrip-tag")

# ── 25. get_task_detail and verify fields ─────────────────────────────────────
if rt_id:
    detail = check("get_task_detail(roundtrip)",
                   lambda: get_task_detail(project_id=rt_pid, task_id=rt_id))
    if detail and not detail.get("error"):
        assert_result("  title matches", detail,
                      "🎯" in detail.get("title", ""), f"title={detail.get('title')}")
        assert_result("  content present", detail,
                      len(detail.get("content", "")) > 10)
        assert_result("  priority=3", detail,
                      detail.get("priority") == 3)
        assert_result("  timeZone=Europe/Paris", detail,
                      detail.get("timeZone") == "Europe/Paris",
                      f"tz={detail.get('timeZone')}")
        assert_result("  tags present", detail,
                      "roundtrip-tag" in (detail.get("tags") or []),
                      f"tags={detail.get('tags')}")
        assert_result("  reminders present", detail,
                      isinstance(detail.get("reminders"), list)
                      and len(detail.get("reminders", [])) >= 2,
                      f"reminders={detail.get('reminders')}")
        assert_result("  checklist items present", detail,
                      isinstance(detail.get("items"), list)
                      and len(detail.get("items", [])) >= 3,
                      f"items count={len(detail.get('items', []))}")
        assert_result("  kind=CHECKLIST", detail,
                      detail.get("kind") == "CHECKLIST",
                      f"kind={detail.get('kind')}")
        # verify checklist_progress computed
        assert_result("  checklist_progress present", detail,
                      detail.get("checklist_progress") is not None,
                      f"progress={detail.get('checklist_progress')}")

# ══════════════════════════════════════════════════════════════════════════════
#  NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n    Nettoyage : {len(_task_cleanup)} tâches, {len(_proj_cleanup)} projets")
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
