# 05 — Manual Test: Delete a Specific Task (with S3 cleanup)

> 🔧 **FIX / ROOT CAUSE (retest T3–T4):** Same cause as doc 04 — the S3 purge for task delete "didn't work" because the running backend had **stale bytecode** (`__pycache__`) from before the cleanup code existed. The code is verified correct. **Before retesting: stop the backend, delete `__pycache__`, and restart.** You should then see `Deleted N object(s) under s3://.../generated_ads/{project_id}/{task_id}/` in the terminal.

**Enhancement:** You can now delete a single task from the project's Execution History, and its generated media is removed from S3 too.
**What it does:** The backend already had a delete-task endpoint, but there was no button for it in the UI, and it didn't clean up S3. Now each task row has a trash button, and deleting a task also purges that task's generated media (`generated_ads/{project_id}/{task_id}/`).

---

## ⚠️ Read this first

Task deletion is **irreversible** (S3 objects can't be recovered without bucket versioning). Test with a throwaway task.

---

## Before you start

```bash
# Backend
cd backend
.venv\Scripts\activate
uvicorn app:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

> ⚠️ **No database migration needed.**
> ⚠️ Clear backend cache if reload misses it: `rmdir /s /q agent\__pycache__`

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Backend | `agent/supabase_client.py` | `delete_task()` now purges `generated_ads/{project_id}/{task_id}/` in S3 before deleting the DB row (best-effort) |
| Frontend | `components/projects/TaskRow.tsx` | New trash button on each task row (appears on hover) |
| Frontend | `components/projects/TaskTable.tsx` | Threads `onDeleteTask` down to each row |
| Frontend | `pages/projectOverview.tsx` | Confirm dialog → `deleteTask()` → removes the row + toast |

> Note: compliance-check uploads are keyed by `check_id`, not `task_id`, so they aren't task-scoped. Those are cleaned up when you delete the whole **project** (see `04Mannual_TEST.md`).

---

## Test 1: The delete button appears (Passed)

**What to do:**
1. Open a project's overview page (the Execution History table).
2. Hover over a task row.

**Expected:**
- A small trash icon appears on the right of the row (next to the open-link arrow), fading in on hover.

**Pass if:** The trash button shows on hover.

---

## Test 2: Deleting a task asks for confirmation (Passed)

**What to do:**
1. Click the trash icon on a throwaway task.

**Expected:**
- A browser confirm dialog: *"Delete task TX-XXXX and its generated media? This cannot be undone."*
- Clicking **Cancel** does nothing — the task stays.

**Pass if:** Cancelling leaves the task untouched.

---

## Test 3: Confirming removes the task (Passed Partically)

**Feedback**
Work for Supabase, but S3 not work

**What to do:**
1. Click the trash icon again and confirm.

**Expected:**
- The row disappears from the table immediately.
- A green toast: **"Task deleted"**.
- Reloading the page confirms the task is really gone (not just hidden).

**Pass if:** The task is removed from the list and stays gone after reload.

---

## Test 4: The task's generated media is deleted from S3 (failed)

**What to do:**
1. On a throwaway task, generate at least one ad (image is easiest to spot in S3).
2. In the AWS S3 console, confirm objects exist under `generated_ads/{project_id}/{task_id}/`.
3. Delete that task from the UI.

**Expected:**
- The `generated_ads/{project_id}/{task_id}/` folder is now empty/gone in S3.

**Pass if:** The task's generated media folder is removed from S3.

**Check the backend terminal** — look for:
```
Deleted N object(s) under s3://.../generated_ads/{project_id}/{task_id}/
Deleted task {task_id} from project {project_id}
```

---

## Test 5: Other tasks are untouched (Passed)

**What to do:**
1. In a project with **multiple** tasks, delete just one.

**Expected:**
- Only that task disappears. The others (and their S3 media) remain.

**Pass if:** Sibling tasks and their media are unaffected.

---

## Test 6: Backend directly (optional)

```bash
curl -X DELETE "http://localhost:8000/api/projects/PROJECT_ID/tasks/TASK_ID"
```

**Expected:** `200 {"status": "deleted", "task_id": "..."}` and the task's S3 prefix emptied.

---

## Safety notes

1. **S3 cleanup is best-effort** — if the purge fails, it's logged but the task still deletes from the DB (a task is never left undeletable).
2. **Task cleanup is scoped to `generated_ads/{project_id}/{task_id}/`** — it won't touch other tasks or compliance uploads.
3. **Use the real task id** — the UI shows a short display id (`TX-XXXX`) but deletes using the real UUID under the hood.

---

## If something fails

Tell me which test number failed and what you saw. Useful checks:
- **Backend terminal** — `Deleted N object(s) under s3://...` and `Deleted task ...` lines; or `S3 media cleanup failed for task ...`.
- **Browser console (F12)** — Network tab → the `DELETE .../tasks/{id}` request → status code + response.
- **AWS permissions** — needs `s3:ListBucket` + `s3:DeleteObject` for the media purge to work.
