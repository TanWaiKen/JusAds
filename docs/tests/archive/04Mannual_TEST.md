# 04 — Manual Test: Delete Project Cleans Up S3 Media

> 🔧 **FIX / ROOT CAUSE (retest all):** In the previous round the S3 media was **not** deleted and no S3 log lines appeared. Root cause: the running backend was executing **stale bytecode** (`__pycache__`) from before the S3-cleanup code was added — so the new code never ran. The S3 code itself is verified working (it correctly lists the exact `generated_ads/{project_id}/...` keys and would delete them). **Before retesting: stop the backend, delete `__pycache__`, and restart.** Then the delete will purge S3 and you'll see `delete_project_media: removed N S3 object(s)` in the terminal.

**Enhancement:** When you delete a project, its S3 media is now deleted too — not just the database rows.
**What it does:** Previously, deleting a project removed the Supabase records (cascading to tasks, checks, violations) but left every generated ad, reference image, and compliance upload orphaned in the S3 bucket forever. Now the project's S3 media is purged as part of deletion.

---

## ⚠️ Read this first — deletion is irreversible

S3 object deletion **cannot be undone** unless your bucket has versioning enabled. Test this with a **throwaway project**, not one whose media you care about.

---

## Before you start

Start both servers manually:

```bash
# Backend
cd backend
.venv\Scripts\activate
uvicorn app:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

> ⚠️ **No database migration needed.** This only changes deletion behavior.
> ⚠️ Clear backend cache if reload misses it: `rmdir /s /q agent\__pycache__`

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Backend | `agent/s3_client.py` | New `delete_prefix(prefix)` (paginated batch delete, refuses empty prefix) and `delete_project_media(project_id, owner_email)` (purges all project-scoped prefixes) |
| Backend | `agent/supabase_client.py` | `delete_project()` now resolves the owner, purges S3 media, **then** deletes the DB row |

### Which S3 prefixes get purged

| Prefix | Contains |
|--------|----------|
| `generated_ads/{project_id}/` | Generated ads (text/image/audio/video) + uploaded chat references |
| `uploads/{owner_email}/{project_id}/` | Compliance-check source uploads |
| `remixed/{owner_email}/{project_id}/` | Remediated / remixed outputs |
| `segmented/{owner_email}/{project_id}/` | Segmented + mask images |

The `generated_ads/` prefix is keyed only by project. The other three embed the owner's email, so they're purged using the project's resolved `owner_email`.

---

## Test 1: Generated ad media is deleted with the project (Failed)

**Feedback**


Addtional
The response of chatbot not fit the request, but the final campaign result is correct Generate me text of showing a travel package to Bali
Based on your request and the provided guides, I will generate ad creatives suitable for Static Posters/Banners and Short-Form Video Ads (e.g., TikTok/Reels).

**What to do:**
1. Create a **throwaway** project.
2. Open a generation task and generate at least one ad (text is fine and fast; an image is more visible in S3).
3. In Supabase → `generated_ads`, note the `s3_media_key` for your ad (it starts with `generated_ads/{project_id}/`).
4. In the **AWS S3 console**, browse to `generated_ads/{project_id}/` and confirm the file is there.
5. Back in the app, **delete the project**.

**Expected:**
- The project disappears from the UI.
- In S3, the entire `generated_ads/{project_id}/` folder is now gone (no objects under that prefix).

**Pass if:** The generated media folder no longer exists in S3 after deletion.

**Check the backend terminal** — you should see a log like:
```
delete_project_media: removed N S3 object(s) for project {project_id}
Deleted project {project_id}
```

---

## Test 2: Compliance upload media is deleted too (Failed)

**What to do:**
1. On a throwaway project, run a **compliance check** by uploading an image/video (this stores under `uploads/{owner_email}/{project_id}/`).
2. In S3, confirm objects exist under `uploads/{your_email}/{project_id}/`.
3. Delete the project.

**Expected:**
- The `uploads/{owner_email}/{project_id}/` folder is gone.
- If remediation/segmentation ran, `remixed/...` and `segmented/...` for that project are gone as well.

**Pass if:** Compliance-related media for the project is removed from S3.

---

## Test 3: Deletion still succeeds if S3 cleanup has nothing to do (Failed, Onlyu show remove from supabase)

**What to do:**
1. Create a project but **don't generate anything**.
2. Delete it.

**Expected:**
- Project deletes normally, no error.
- Backend log shows `removed 0 S3 object(s)`.

**Pass if:** A project with no media deletes cleanly.

---

## Test 4: A storage hiccup doesn't block deletion (safety behavior)

This is by design, not something you need to force: if S3 is unreachable or a purge fails, the error is **logged** but the project is **still deleted** from the database. You'd see a log line like `S3 media cleanup failed for project ...` followed by `Deleted project ...`.

**Pass if:** You understand that DB deletion is never blocked by an S3 problem (media may be left behind and logged, rather than making the project undeletable).

---

## Test 5: Backend directly (optional)

```bash
curl -X DELETE "http://localhost:8000/api/projects/PROJECT_ID"
```

**Expected:** `200 {"status": "deleted", "project_id": "..."}`, and the S3 prefixes above emptied.

---

## Safety notes (how this was built defensively)

1. **`delete_prefix` refuses a blank prefix** — it raises rather than risk targeting the whole bucket.
2. **Owner is resolved before the DB delete** — the owner-scoped compliance keys can't be reconstructed once the row is gone.
3. **Each prefix is purged independently** — a failure on one doesn't stop the others.
4. **S3 cleanup is best-effort** — it never prevents the project from being deleted.

---

## If something fails

Tell me which test number failed and what you saw. Useful checks:
- **Backend terminal** — look for `delete_project_media`, `Deleted N object(s) under s3://...`, and any `delete_prefix failed` / `S3 media cleanup failed` lines.
- **AWS creds/permissions** — the app's IAM identity needs `s3:ListBucket` and `s3:DeleteObject` on the bucket. If cleanup logs a permissions error, that's why media remains.
- **Wrong prefix** — if media survives, confirm the actual S3 key structure matches the prefixes in the table above.
