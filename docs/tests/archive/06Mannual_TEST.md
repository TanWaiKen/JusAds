# 06 — Manual Test: Bug Fixes Retest (Video V2 + S3 Deletion)

This doc re-tests the two things that failed in docs 03/04/05. Both are now fixed. Do the **one-time setup** first — it's the whole reason they failed before.

---

## 🔧 What was wrong and what changed

| # | Symptom (before) | Root cause | Fix |
|---|------------------|-----------|-----|
| 1 | Video V2 crashed: `'bool' object has no attribute 'generate'`, 0 ads | The imported module `video_v2` was shadowed by the `video_v2` boolean parameter, so `.generate` ran on `True` | Module now imported as `video_v2_agent` |
| 2 | Project/Task delete removed the DB row but **not** S3 media, and no S3 logs appeared | The running backend was executing **stale `__pycache__` bytecode** from before the S3-cleanup code was added | Code verified correct; cache cleared |

> The S3 code was already correct — a live check confirmed it lists and would delete the exact `generated_ads/{project_id}/{task_id}/...` keys. The only problem was the old bytecode still running.

---

## ⚠️ ONE-TIME SETUP (do this before anything else)

The backend **must** be restarted on fresh code, or you'll retest the old broken behavior again.

1. **Stop** the running backend (Ctrl+C in its terminal).
2. **Clear the Python cache** (from `backend/`):

   PowerShell:
   ```powershell
   Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName -notmatch '\.venv' } | Remove-Item -Recurse -Force
   ```
   (or CMD, per folder: `rmdir /s /q agent\__pycache__` and `rmdir /s /q jusads_generation\__pycache__`)

3. **Restart** both servers:
   ```bash
   # Backend
   cd backend
   .venv\Scripts\activate
   uvicorn app:app --reload --port 8000

   # Frontend
   cd frontend
   npm run dev
   ```

> ⚠️ Video V2 still needs `VERTEX_PROJECT_ID` set + Veo enabled, and `ffmpeg`/`ffprobe` on PATH.
> ⚠️ S3 delete tests are **irreversible** — use throwaway projects/tasks.

---

# PART A — Video V2 Fix (re-tests 03 B3–B5)

## Test A1: Video V2 no longer crashes

**What to do:**
1. Open **Settings** → turn **Video V2 — Multi-Scene** ON → close.
2. Type: `Generate a TikTok video ad for a new energy drink, energetic and youthful`
3. Watch the backend terminal.

**Expected:**
- **No** `'bool' object has no attribute 'generate'` error.
- You see `[Orchestrator] Using Video V2 (multi-scene storyboard)` followed by `[VideoAgentV2]` phase logs:
  `Director planned N scene(s)` → `Keyframe i generated` → `Submitting Veo clip i` → `Burnt subtitle into scene i` → `Combined N clips with xfade transitions` → `Voiceover merged`.

**Pass if:** Generation runs through the V2 pipeline without the crash. (It's slow — several minutes — that's normal.)

---

## Test A2: The V2 video is multi-scene

**What to do:**
1. Wait for the video to appear in the Output Gallery and play it.

**Expected:**
- Multiple distinct scenes with motion.
- Burnt-in subtitle captions near the bottom (white text on translucent box).
- Cross-dissolve transitions between scenes.
- One voiceover across the whole ad.

**Verify (optional):** Supabase → `generated_ads` → your row → `metadata` has `"generation_method": "veo_multi_scene_v2"`, a `scene_count`, and a `scenes` array.

**Pass if:** The video is clearly multi-scene with captions, transitions, and voiceover.

---

## Test A3: Reference image anchors V2 scenes (bonus)

**What to do:**
1. Upload a product image → turn Video V2 ON → `Make a short video ad for this product`.

**Expected:** The scenes feature your product.

**Pass if:** Your product appears across the generated scenes.

---

# PART B — Project Delete → S3 (re-tests 04)

## Test B1: Deleting a project purges its S3 media

**What to do:**
1. Create a **throwaway** project, generate at least one ad (an image is easy to spot).
2. In AWS S3, confirm objects exist under `generated_ads/{project_id}/`.
3. Delete the project from the UI.
4. Watch the backend terminal.

**Expected:**
- Terminal shows:
  ```
  Deleted N object(s) under s3://.../generated_ads/{project_id}/
  delete_project_media: removed N S3 object(s) for project {project_id}
  Deleted project {project_id}
  ```
- In S3, `generated_ads/{project_id}/` is now empty/gone.

**Pass if:** The S3 folder is gone AND you see the `removed N S3 object(s)` log.

---

## Test B2: Empty project shows the S3 log too

**What to do:**
1. Create a project, generate **nothing**, delete it.

**Expected:**
- Terminal shows `delete_project_media: removed 0 S3 object(s) for project ...` (this line proves the new code is running — its absence was the original bug).

**Pass if:** You see the `removed 0 S3 object(s)` line.

---

## Test B3: Compliance uploads are purged (if any)

**What to do:**
1. On a throwaway project, run a **compliance check** with an uploaded image/video.
2. Confirm objects under `uploads/{your_email}/{project_id}/` in S3.
3. Delete the project.

**Expected:** `uploads/...`, and any `remixed/...` / `segmented/...` for that project, are removed.

**Pass if:** Compliance-related media for the project is gone from S3.

---

# PART C — Task Delete → S3 (re-tests 05)

## Test C1: Deleting a task purges its S3 media

**What to do:**
1. On a throwaway task, generate at least one ad.
2. Confirm objects under `generated_ads/{project_id}/{task_id}/` in S3.
3. Delete the task (trash icon on the row → confirm).
4. Watch the backend terminal.

**Expected:**
- Terminal shows:
  ```
  Deleted N object(s) under s3://.../generated_ads/{project_id}/{task_id}/
  Deleted task {task_id} from project {project_id}
  ```
- In S3, `generated_ads/{project_id}/{task_id}/` is empty/gone.

**Pass if:** The task's S3 folder is removed AND the log line appears.

---

## Test C2: Sibling tasks and their media survive

**What to do:**
1. In a project with multiple tasks (each with media), delete just one.

**Expected:** Only the deleted task's `.../{task_id}/` prefix is removed; other tasks' media remains.

**Pass if:** Sibling tasks and their S3 media are untouched.

---

## Quick sanity: how to confirm the fix is actually loaded

If S3 delete "still doesn't work," the backend is almost certainly running old bytecode again. Confirm by watching the terminal on **any** delete — if you do **not** see a line containing `delete_project_media` (project) or `Deleted N object(s) under s3://` (task), the new code isn't loaded: stop the server, clear `__pycache__`, restart.

---

## If something fails

Tell me which test number failed and paste the backend terminal lines. Useful markers:
- Video V2: `[Orchestrator] Using Video V2`, `[VideoAgentV2] ...`
- Project delete: `delete_project_media: removed N S3 object(s)`
- Task delete: `Deleted N object(s) under s3://.../{task_id}/`
- Permissions: an S3 `AccessDenied` means the IAM identity lacks `s3:ListBucket` / `s3:DeleteObject`.
