# TickTick API — Complete Endpoint Reference

> Compiled from the official Open API docs, the `ticktick-sdk` reverse-engineered V2 internals, and multiple open-source MCP implementations.

---

## Overview: Two APIs

| Aspect | V1 (Official Open API) | V2 (Unofficial / Web API) |
|--------|------------------------|---------------------------|
| **Base URL** | `https://api.ticktick.com/open/v1` | `https://api.ticktick.com/api/v2` |
| **Alt Host** | `https://api.dida365.com/open/v1` | `https://api.dida365.com/api/v2` |
| **Auth** | OAuth2 Bearer Token | Session Token (cookies, `t` cookie primary) |
| **Scopes** | `tasks:read`, `tasks:write` | N/A (full access once signed in) |
| **Coverage** | Tasks + Projects only | Full: Tasks, Projects, Folders, Tags, Habits, Focus, Columns, User stats |
| **Stability** | Official, versioned | Undocumented, may change |

---

## V1 API Endpoints (Official)

All paths relative to `https://api.ticktick.com/open/v1`.
Auth header: `Authorization: Bearer {access_token}`

### Tasks

#### Get Task
```
GET /project/{projectId}/task/{taskId}
```
**Params:** `projectId` (path, required), `taskId` (path, required)
**Response:** Task object (see [Task Schema](#task-schema))

#### Create Task
```
POST /task
```
**Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | **Yes** | Task title |
| `projectId` | string | No | Project ID (defaults to inbox if omitted) |
| `content` | string | No | Task content / notes |
| `desc` | string | No | Description of checklist |
| `isAllDay` | boolean | No | All-day flag |
| `startDate` | date | No | `"yyyy-MM-dd'T'HH:mm:ssZ"` format |
| `dueDate` | date | No | `"yyyy-MM-dd'T'HH:mm:ssZ"` format |
| `timeZone` | string | No | IANA timezone e.g. `"America/Los_Angeles"` |
| `reminders` | list[string] | No | `["TRIGGER:P0DT9H0M0S", "TRIGGER:PT0S"]` |
| `repeatFlag` | string | No | RRULE format e.g. `"RRULE:FREQ=DAILY;INTERVAL=1"` |
| `priority` | integer | No | `0` (none), `1` (low), `3` (medium), `5` (high) |
| `sortOrder` | integer | No | Sort order value |
| `items` | list[object] | No | Checklist sub-items (see [ChecklistItem](#checklistitem-schema)) |

**Response:** Created Task object

#### Update Task
```
POST /task/{taskId}
```
**Params:** `taskId` (path, required)
**Body:** Same fields as Create, plus:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | **Yes** | Task ID |
| `projectId` | string | **Yes** | Project ID |

**Note:** V1 uses POST (not PUT) for updates. Sends full task object.
**Response:** Updated Task object

#### Complete Task
```
POST /project/{projectId}/task/{taskId}/complete
```
**Params:** `projectId` (path, required), `taskId` (path, required)
**Response:** No content (200)

#### Delete Task
```
DELETE /project/{projectId}/task/{taskId}
```
**Params:** `projectId` (path, required), `taskId` (path, required)
**Response:** No content (200)

### Projects

#### List All Projects
```
GET /project
```
**Response:** Array of Project objects (see [Project Schema](#project-schema))

#### Get Project by ID
```
GET /project/{projectId}
```
**Params:** `projectId` (path, required)
**Response:** Project object

#### Get Project With Data (tasks + columns)
```
GET /project/{projectId}/data
```
**Params:** `projectId` (path, required)
**Response:** ProjectData object containing:
```json
{
  "project": { Project },
  "tasks": [ Task, ... ],      // Undone tasks only
  "columns": [ Column, ... ]   // Kanban columns
}
```

#### Create Project
```
POST /project
```
**Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Project name |
| `color` | string | No | Hex color e.g. `"#F18181"` |
| `sortOrder` | integer | No | Sort order |
| `viewMode` | string | No | `"list"`, `"kanban"`, `"timeline"` |
| `kind` | string | No | `"TASK"` or `"NOTE"` |

**Response:** Created Project object

#### Update Project
```
POST /project/{projectId}
```
**Params:** `projectId` (path, required)
**Body:** Same fields as Create
**Response:** Updated Project object

#### Delete Project
```
DELETE /project/{projectId}
```
**Params:** `projectId` (path, required)
**Response:** No content (200)

---

## V2 API Endpoints (Unofficial / Reverse-Engineered)

All paths relative to `https://api.ticktick.com/api/v2`.
Auth: Session cookies (`Cookie: t={session_token}`) + special headers:
```
User-Agent: Mozilla/5.0 (rv:145.0) Firefox/145.0
X-Device: {"platform":"web","version":6430,"id":"{24-char-hex-device-id}"}
Cookie: t={session_token}
```

### Authentication

#### Sign In
```
POST /user/signon?wc=true&remember=true
```
**Body:**
```json
{ "username": "email@example.com", "password": "password" }
```
**Response:**
```json
{
  "token": "jwt...",
  "userId": 123456,
  "username": "email@example.com",
  "inboxId": "inbox123456",
  "pro": true
}
```
Also sets cookies: `t` (session token), `AWSALB`, `AWSALBCORS`.

**2FA flow:** If account has 2FA, response contains `{ "authId": "...", "expireTime": 300 }` instead. Then:
```
POST /user/sign/mfa/code/verify
Headers: x-verify-id: {authId}
Body: { "code": "123456", "method": "app" }
```

### Sync (Full State)

#### Get All Data
```
GET /batch/check/0
```
**Response:**
```json
{
  "inboxId": "inbox123456",
  "projectProfiles": [ Project, ... ],
  "projectGroups": [ ProjectGroup, ... ],
  "syncTaskBean": {
    "update": [ Task, ... ]   // All active tasks
  },
  "tags": [ Tag, ... ],
  "checkPoint": 1705678901234
}
```
This is the **only way to list ALL tasks at once** (V1 can only list per-project).

### Tasks

#### Get Task (no project ID needed)
```
GET /task/{taskId}
```
**Response:** Task V2 object (richer than V1, includes `tags`, `parentId`, `childIds`, `columnId`, `pinnedTime`)

#### Batch Task Operations (create / update / delete)
```
POST /batch/task
```
**Body:**
```json
{
  "add": [
    {
      "title": "New Task",
      "projectId": "proj123",
      "content": "notes",
      "priority": 5,
      "tags": ["work", "urgent"],
      "startDate": "2026-01-20T09:00:00.000+0000",
      "dueDate": "2026-01-20T17:00:00.000+0000",
      "timeZone": "America/Los_Angeles",
      "isAllDay": false,
      "reminders": [{"id": "...", "trigger": "TRIGGER:-PT30M"}],
      "repeatFlag": "RRULE:FREQ=DAILY",
      "items": [{"title": "Subtask 1", "status": 0}],
      "sortOrder": 0,
      "kind": "TEXT"
    }
  ],
  "update": [
    {
      "id": "task456",
      "projectId": "proj123",
      "title": "Updated Title",
      "priority": 3,
      "status": 2,                          // 0=active, 2=completed, -1=abandoned
      "completedTime": "2026-01-17T10:00:00.000+0000",
      "pinnedTime": "2026-01-17T10:00:00.000+0000",  // set to pin, null/empty to unpin
      "columnId": "col123"                  // kanban column assignment
    }
  ],
  "delete": [
    { "projectId": "proj123", "taskId": "task789" }
  ],
  "addAttachments": [],
  "updateAttachments": [],
  "deleteAttachments": []
}
```
**Response:**
```json
{
  "id2etag": { "task456": "a1b2c3d4", "newTaskId": "e5f6g7h8" },
  "id2error": {}
}
```
**⚠️ Warning:** HTTP 200 even on failures — check `id2error` for errors. Silent success for nonexistent resources on delete.

#### Move Tasks Between Projects
```
POST /batch/taskProject
```
**Body:** Array of moves:
```json
[
  { "taskId": "task123", "fromProjectId": "projA", "toProjectId": "projB" }
]
```

#### Set/Unset Subtask Relationships
```
POST /batch/taskParent
```
**Body (set parent):**
```json
[{ "taskId": "child123", "projectId": "proj123", "parentId": "parent456" }]
```
**Body (unset parent):**
```json
[{ "taskId": "child123", "projectId": "proj123", "oldParentId": "parent456" }]
```
**⚠️ Important:** Setting `parentId` during task creation is **IGNORED**. You must create the task first, then call `/batch/taskParent`.

#### Get Completed/Abandoned Tasks
```
GET /project/all/closed?from={from}&to={to}&status={status}&limit={limit}
```
| Param | Type | Description |
|-------|------|-------------|
| `from` | string | Start date `"yyyy-MM-dd HH:mm:ss"` |
| `to` | string | End date `"yyyy-MM-dd HH:mm:ss"` |
| `status` | string | `"Completed"` or `"Abandoned"` |
| `limit` | integer | Max results (default 100) |

**Response:** Array of Task objects

#### Get Deleted Tasks (Trash)
```
GET /project/all/trash/pagination?start={start}&limit={limit}
```
| Param | Type | Description |
|-------|------|-------------|
| `start` | integer | Offset (default 0) |
| `limit` | integer | Max results (default 500) |

### Projects

#### Batch Project Operations
```
POST /batch/project
```
**Body:**
```json
{
  "add": [{
    "name": "New Project",
    "color": "#FF6B6B",
    "kind": "TASK",
    "viewMode": "list",
    "groupId": "folder123"
  }],
  "update": [{
    "id": "proj123",
    "name": "Renamed",
    "color": "#4ECDC4",
    "groupId": "NONE"     // "NONE" to remove from folder
  }],
  "delete": ["proj123"]   // Array of project IDs
}
```
**Response:** `{ "id2etag": {...}, "id2error": {...} }`

### Project Groups (Folders)

#### Batch Folder Operations
```
POST /batch/projectGroup
```
**Body:**
```json
{
  "add": [{ "name": "Work", "listType": "group" }],
  "update": [{ "id": "group123", "name": "Work Renamed" }],
  "delete": ["group123"]
}
```

### Kanban Columns

#### List Columns for a Project
```
GET /column/project/{projectId}
```
**Response:**
```json
[
  { "id": "col123", "projectId": "proj123", "name": "To Do", "sortOrder": 0 },
  { "id": "col456", "projectId": "proj123", "name": "In Progress", "sortOrder": 1 }
]
```

#### Batch Column Operations
```
POST /column
```
**Body:**
```json
{
  "add": [{ "projectId": "proj123", "name": "Review", "sortOrder": 2 }],
  "update": [{ "id": "col123", "projectId": "proj123", "name": "Done", "sortOrder": 3 }],
  "delete": [{ "columnId": "col123", "projectId": "proj123" }]
}
```
**Note:** To move a task to a column, update the task with `"columnId": "col123"` via `/batch/task`.

### Tags

#### Batch Create/Update Tags
```
POST /batch/tag
```
**Body:**
```json
{
  "add": [{
    "label": "Work",
    "name": "work",         // lowercase, auto-generated from label
    "color": "#FF6B6B",
    "parent": "projects"    // optional, for nested tags
  }],
  "update": [{
    "name": "work",
    "color": "#FF5500"
  }]
}
```
**Note:** No delete in batch — use `DELETE /tag` instead.

#### Rename Tag
```
PUT /tag/rename
```
**Body:** `{ "name": "old-name", "newName": "new-label" }`

#### Merge Tags
```
PUT /tag/merge
```
**Body:** `{ "name": "source-tag", "newName": "target-tag" }`
Moves all tasks from source to target tag.

#### Delete Tag
```
DELETE /tag?name={tagName}
```
**Params:** `name` (query, required)

### Habits

#### List All Habits
```
GET /habits
```
**Response:** Array of Habit objects

#### List Habit Sections (time-of-day groupings)
```
GET /habitSections
```
**Response:**
```json
[
  { "id": "sec1", "name": "_morning", "sortOrder": 0 },
  { "id": "sec2", "name": "_afternoon", "sortOrder": 1 },
  { "id": "sec3", "name": "_night", "sortOrder": 2 }
]
```

#### Get Habit Preferences
```
GET /user/preferences/habit?platform=web
```

#### Batch Habit Operations
```
POST /habits/batch
```
**Body:**
```json
{
  "add": [{
    "id": "24-char-hex-client-generated",
    "name": "Exercise",
    "type": "Boolean",       // or "Real" for numeric
    "goal": 1.0,             // for Real: e.g. 30 pages
    "step": 5,               // increment per click (Real only)
    "unit": "Pages",         // unit label (Real only)
    "iconRes": "habit_daily_check_in",
    "color": "#97E38B",
    "status": 0,
    "totalCheckIns": 0,
    "currentStreak": 0,
    "repeatRule": "RRULE:FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA",
    "reminders": ["08:00"],
    "encouragement": "Stay strong!",
    "targetDays": 30
  }],
  "update": [{
    "id": "habit123",
    "name": "Exercise Updated",
    "status": 2              // 0=active, 2=archived
  }],
  "delete": ["habit123"]
}
```

**Habit Repeat Rules:**
| Schedule | RRULE |
|----------|-------|
| Daily (every day) | `RRULE:FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA` |
| Weekdays only | `RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR` |
| Weekends only | `RRULE:FREQ=WEEKLY;BYDAY=SA,SU` |
| X times per week | `RRULE:FREQ=WEEKLY;TT_TIMES=5` |
| Specific days | `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` |

#### Query Habit Check-ins
```
POST /habitCheckins/query
```
**Body:**
```json
{
  "habitIds": ["habit123", "habit456"],
  "afterStamp": 20260101    // YYYYMMDD integer, 0 for all
}
```
**Response:**
```json
{
  "checkins": {
    "habit123": [
      { "habitId": "habit123", "checkinStamp": 20260117, "value": 1.0, "status": 2 }
    ]
  }
}
```

#### Batch Check-in Operations
```
POST /habitCheckins/batch
```
**Body:**
```json
{
  "add": [{
    "id": "24-char-hex",
    "habitId": "habit123",
    "checkinStamp": 20260115,             // YYYYMMDD (supports backdating)
    "checkinTime": "2026-01-15T10:00:00.000+0000",
    "opTime": "2026-01-17T10:00:00.000+0000",
    "value": 1.0,
    "goal": 1.0,
    "status": 2
  }],
  "update": [],
  "delete": ["checkin-id-123"]
}
```

### Focus / Pomodoro

#### Focus Heatmap (like GitHub contribution graph)
```
GET /pomodoros/statistics/heatmap/{from}/{to}
```
Date params in `YYYYMMDD` format. E.g. `/pomodoros/statistics/heatmap/20260101/20260331`

#### Focus Time by Tag
```
GET /pomodoros/statistics/dist/{from}/{to}
```
Date params in `YYYYMMDD` format.
**Response:**
```json
{
  "tagDurations": {
    "work": 7200,       // seconds
    "personal": 3600
  }
}
```

### User & Statistics

#### Get User Status (subscription, inbox ID)
```
GET /user/status
```
**Response:**
```json
{
  "userId": "123456",
  "username": "user@example.com",
  "inboxId": "inbox123456",
  "pro": true,
  "proStartDate": "2024-01-01",
  "proEndDate": "2025-01-01"
}
```

#### Get User Profile
```
GET /user/profile
```

#### Get User Preferences
```
GET /user/preferences/settings?includeWeb=true
```

#### Get Productivity Statistics
```
GET /statistics/general
```
**Response includes:** level, score, tasks completed today, streaks, etc.

---

## Data Schemas

### Task Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Task identifier |
| `projectId` | string | Project ID |
| `title` | string | Task title |
| `content` | string | Task content / notes |
| `desc` | string | Checklist description |
| `kind` | string | V2 only: `"TEXT"`, `"NOTE"`, `"CHECKLIST"` |
| `isAllDay` | boolean | All-day flag |
| `startDate` | string | Start datetime (ISO format) |
| `dueDate` | string | Due datetime (ISO format) |
| `timeZone` | string | IANA timezone |
| `reminders` | list | V1: `["TRIGGER:PT0S"]`; V2: `[{"id":"...", "trigger":"TRIGGER:-PT30M"}]` |
| `repeatFlag` | string | RRULE recurrence rule |
| `repeatFrom` | integer | V2 only: `0`, `1`, `2` |
| `priority` | integer | `0` (none), `1` (low), `3` (medium), `5` (high) |
| `status` | integer | `0` (active), `2` (completed), `-1` (abandoned, V2 only) |
| `completedTime` | string | Completion datetime |
| `sortOrder` | integer | Sort order |
| `items` | list[ChecklistItem] | Subtask checklist items |
| `tags` | list[string] | **V2 only** — tag names |
| `parentId` | string | **V2 only** — parent task ID |
| `childIds` | list[string] | **V2 only** — child task IDs |
| `columnId` | string | **V2 only** — kanban column ID |
| `pinnedTime` | string | **V2 only** — pin timestamp (null if not pinned) |
| `progress` | integer | **V2 only** — 0-100 |
| `deleted` | integer | **V2 only** — `0` or `1` (soft delete / trash) |
| `etag` | string | **V2 only** — concurrency token |
| `focusSummaries` | list | **V2 only** — focus time data |

### ChecklistItem Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Item identifier |
| `title` | string | Item title |
| `status` | integer | `0` (normal), `1` (completed) |
| `sortOrder` | integer | Sort order |
| `startDate` | string | Start datetime |
| `isAllDay` | boolean | All-day flag |
| `timeZone` | string | Timezone |
| `completedTime` | string | Completion datetime |

### Project Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Project identifier |
| `name` | string | Project name |
| `color` | string | Hex color |
| `sortOrder` | integer | Sort order |
| `closed` | boolean | Whether project is closed/archived |
| `groupId` | string | Folder/group ID |
| `viewMode` | string | `"list"`, `"kanban"`, `"timeline"` |
| `permission` | string | `"read"`, `"write"`, `"comment"` |
| `kind` | string | `"TASK"` or `"NOTE"` |

### Column Schema (Kanban)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Column identifier |
| `projectId` | string | Parent project |
| `name` | string | Column name |
| `sortOrder` | integer | Sort order |

### Tag Schema (V2 only)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Lowercase identifier |
| `label` | string | Display name |
| `color` | string | Hex color |
| `parent` | string | Parent tag name (for hierarchy) |

### ProjectGroup / Folder Schema (V2 only)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Group identifier |
| `name` | string | Folder name |
| `listType` | string | Always `"group"` |

---

## Quick Reference: V1 vs V2 Feature Matrix

| Feature | V1 Open API | V2 Web API |
|---------|:-----------:|:----------:|
| **Tasks CRUD** | ✅ | ✅ (batch) |
| **Complete Task** | ✅ (dedicated endpoint) | ✅ (status=2 via batch) |
| **List ALL Tasks** | ❌ (per-project only) | ✅ (`/batch/check/0`) |
| **Task Tags** | ❌ | ✅ |
| **Subtask Hierarchy** | ❌ (checklist items only) | ✅ (`/batch/taskParent`) |
| **Move Task** | ❌ | ✅ (`/batch/taskProject`) |
| **Pin/Unpin Task** | ❌ | ✅ (`pinnedTime` via batch) |
| **Completed Tasks** | ❌ | ✅ (`/project/all/closed`) |
| **Deleted Tasks (Trash)** | ❌ | ✅ (`/project/all/trash/pagination`) |
| **Projects CRUD** | ✅ | ✅ (batch) |
| **Project With Tasks+Columns** | ✅ (`/data`) | ❌ (use sync) |
| **Folders** | ❌ | ✅ (`/batch/projectGroup`) |
| **Kanban Columns** | Read only (via `/data`) | ✅ Full CRUD (`/column`) |
| **Tags** | ❌ | ✅ Full (create/update/rename/merge/delete) |
| **Habits** | ❌ | ✅ Full CRUD + check-ins |
| **Focus / Pomodoro** | ❌ | ✅ (read heatmap + by-tag stats) |
| **User Profile/Status** | ❌ | ✅ |
| **Productivity Stats** | ❌ | ✅ (`/statistics/general`) |
| **Search Tasks** | ❌ | Via sync + client-side filter |

---

## API Quirks & Important Notes

1. **Recurrence requires `startDate`** — If you set `repeatFlag` without `startDate`, TickTick silently ignores the recurrence.
2. **Subtask `parentId` ignored on creation** — You must create the task first, then call `/batch/taskParent`.
3. **Soft delete** — Deleting tasks moves them to trash (`deleted=1`), not permanent removal.
4. **Date clearing** — To clear `dueDate`, you must also clear `startDate`.
5. **Tag order not preserved** — Tags may return in any order.
6. **Inbox is special** — Cannot be deleted; get its ID via `/user/status` (V2) or from sync data.
7. **V1 empty response quirk** — Returns HTTP 200 with empty body for nonexistent resources (not 404).
8. **V2 batch silent failures** — Batch ops return HTTP 200 even for nonexistent resources. Always check `id2error`.
9. **Tag `name` vs `label`** — `name` is the lowercase identifier, `label` is the display name.
10. **V2 device ID** — Must be 24-character hex string (MongoDB ObjectId format).
11. **Free tier limits** — 99 tasks/list, 9 lists, 19 tags, limited habits.
12. **V2 date format** — Tasks use `"yyyy-MM-dd'T'HH:mm:ss.SSS+0000"`, query params use `"yyyy-MM-dd HH:mm:ss"`, stats use `YYYYMMDD` integer.
13. **Task status values** — `0` = active, `2` = completed, `-1` = abandoned (V2 only), `1` = completed alt (V2).

---

## Endpoint Summary Tables

### V1 Endpoints (11 total)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/project/{projectId}/task/{taskId}` | Get single task |
| POST | `/task` | Create task |
| POST | `/task/{taskId}` | Update task |
| POST | `/project/{projectId}/task/{taskId}/complete` | Complete task |
| DELETE | `/project/{projectId}/task/{taskId}` | Delete task |
| GET | `/project` | List all projects |
| GET | `/project/{projectId}` | Get single project |
| GET | `/project/{projectId}/data` | Get project with tasks + columns |
| POST | `/project` | Create project |
| POST | `/project/{projectId}` | Update project |
| DELETE | `/project/{projectId}` | Delete project |

### V2 Endpoints (25+ total)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **Auth** | | |
| POST | `/user/signon` | Username/password login |
| POST | `/user/sign/mfa/code/verify` | Complete 2FA |
| **Sync** | | |
| GET | `/batch/check/0` | Full state sync (all data) |
| **Tasks** | | |
| GET | `/task/{id}` | Get single task (no project ID needed) |
| POST | `/batch/task` | Create / update / delete tasks (batch) |
| POST | `/batch/taskProject` | Move tasks between projects |
| POST | `/batch/taskParent` | Set / unset subtask relationships |
| GET | `/project/all/closed` | Get completed / abandoned tasks |
| GET | `/project/all/trash/pagination` | Get deleted tasks (trash) |
| **Projects** | | |
| POST | `/batch/project` | Create / update / delete projects (batch) |
| **Folders** | | |
| POST | `/batch/projectGroup` | Create / update / delete folders (batch) |
| **Columns** | | |
| GET | `/column/project/{projectId}` | List kanban columns |
| POST | `/column` | Create / update / delete columns (batch) |
| **Tags** | | |
| POST | `/batch/tag` | Create / update tags |
| PUT | `/tag/rename` | Rename tag |
| PUT | `/tag/merge` | Merge tags |
| DELETE | `/tag` | Delete tag (query param: name) |
| **Habits** | | |
| GET | `/habits` | List all habits |
| GET | `/habitSections` | List habit sections |
| GET | `/user/preferences/habit` | Habit preferences |
| POST | `/habits/batch` | Create / update / delete habits |
| POST | `/habitCheckins/query` | Query check-in records |
| POST | `/habitCheckins/batch` | Create / update / delete check-ins |
| **Focus** | | |
| GET | `/pomodoros/statistics/heatmap/{from}/{to}` | Focus heatmap |
| GET | `/pomodoros/statistics/dist/{from}/{to}` | Focus time by tag |
| **User** | | |
| GET | `/user/status` | Account status (Pro, inbox ID) |
| GET | `/user/profile` | User profile |
| GET | `/user/preferences/settings` | User preferences |
| GET | `/statistics/general` | Productivity statistics |

---

## What Your Current MCP Server Covers

Your existing `ticktick_mcp` implements **9 tools** using **V1 only**:

| Current Tool | V1 Endpoint Used |
|-------------|-----------------|
| `list_projects` | `GET /project` |
| `get_inbox` | `GET /project/inbox/data` (special) |
| `get_project_tasks` | `GET /project/{id}/data` |
| `get_task_detail` | `GET /project/{id}/task/{id}` |
| `create_task` | `POST /task` |
| `update_task` | `POST /project/{id}/task/{id}` (read-modify-write) |
| `complete_task` | Faked via update (status=2), not using `/complete` endpoint |
| `reopen_task` | Faked via update (status=0) |
| `delete_task` | `DELETE /project/{id}/task/{id}` |

### Expansion Opportunities (V1-only, no V2 needed)

These can be added using just your existing V1 auth:

1. **`create_project`** — `POST /project`
2. **`update_project`** — `POST /project/{projectId}`
3. **`delete_project`** — `DELETE /project/{projectId}`
4. **Use dedicated complete endpoint** — `POST /project/{projectId}/task/{taskId}/complete`

### Expansion Opportunities (Requires V2 auth)

Adding V2 session auth would unlock:

1. **List ALL tasks** — `GET /batch/check/0`
2. **Tags** — full CRUD via `/batch/tag`, `/tag/rename`, `/tag/merge`, `DELETE /tag`
3. **Move tasks** — `/batch/taskProject`
4. **Subtask hierarchy** — `/batch/taskParent`
5. **Kanban columns** — `/column/project/{id}`, `POST /column`
6. **Folders** — `/batch/projectGroup`
7. **Completed/abandoned/deleted tasks** — `/project/all/closed`, `/project/all/trash/pagination`
8. **Habits** — full CRUD + check-ins
9. **Focus stats** — heatmap + by-tag
10. **User profile & stats** — `/user/status`, `/statistics/general`
11. **Batch operations** — create/update/delete multiple tasks/projects in one call
12. **Pin/unpin tasks** — via `pinnedTime` field in batch update

---

*Sources: TickTick Open API docs (via developer.ticktick.com), [ticktick-sdk](https://github.com/dev-mirzabicer/ticktick-sdk) API_INTERNALS.md, [jacepark12/ticktick-mcp](https://github.com/jacepark12/ticktick-mcp), [Code-MonkeyZhang/ticktick-mcp-enhanced](https://github.com/Code-MonkeyZhang/ticktick-mcp-enhanced)*
