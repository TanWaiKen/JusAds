# 07 — Manual Test: Video V2 Planning Flow (Storyboard → Continue) + Malaysia Localization

This round does three things:

1. **Fixes the keyframe crash** (`400 INVALID_ARGUMENT`) — the lite image model rejected `2K`; now uses `1K` (like the working image agent), plus retry/throttle for `429` quota errors.
2. **Adds a two-phase planning flow** — Video V2 first plans a **storyboard** (scenes + keyframes), shows it with a **Continue** button, and only renders the expensive Veo clips after you approve. Each scene carries its own **shot type, camera movement, script line, SFX plan, subtitle, and duration**.
3. **Localizes everything to Malaysia** — all prompts (image, keyframes, scripts, voiceover) now target the Malaysian multicultural market (Malay, Chinese, Indian), local settings, Bahasa/Manglish copy, and cultural do's/don'ts.

---

## ⚠️ ONE-TIME SETUP (must do)

The backend must run fresh code:

1. **Stop** the backend (Ctrl+C).
2. **Clear cache** (from `backend/`):
   ```powershell
   Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName -notmatch '\.venv' } | Remove-Item -Recurse -Force
   ```
3. **Restart** both servers (backend `uvicorn app:app --reload --port 8000`, frontend `npm run dev`).

> ⚠️ Needs `VERTEX_PROJECT_ID` + Veo enabled, and `ffmpeg`/`ffprobe` on PATH.
> ⚠️ Enough Gemini image quota — the plan renders one keyframe per scene (2–5).

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Backend | `jusads_generation/agents/video_v2.py` | Keyframe `image_size="1K"` fix + 429 retry/backoff + throttle; richer `Scene` (shot_type, camera_movement, script, sfx); Malaysia localization block; per-scene SFX bed + combined audio mix; new `plan_video()` and `execute_video_plan()` |
| Backend | `jusads_generation/orchestrator.py` | Video V2 now runs in **plan mode** during chat (emits `video_plan`); new `run_video_plan_execution()` for the Continue step |
| Backend | `routes/generation.py` | New `POST /execute-video-plan` endpoint |
| Frontend | `services/generationApi.ts` | `VideoPlan` types, `normalizeVideoPlan()`, `executeVideoPlan()` |
| Frontend | `components/workspace/canvas/VideoPlanStoryboard.tsx` | **New** storyboard board with per-scene cards + Continue button |
| Frontend | `components/workspace/canvas/ChatbotPanel.tsx` | Captures `video_plan`, renders storyboard, handles Continue |

---

## Test 1: Keyframe generation no longer 400s

**What to do:**
1. Settings → **Video V2 — Multi-Scene** ON.
2. Type: `Generate a TikTok video ad for a new kopi drink, energetic and youthful`
3. Watch the backend terminal.

**Expected:**
- `[VideoAgentV2] Director planned N scene(s)`
- `[VideoAgentV2] Keyframe 0 generated`, `Keyframe 1 generated`, ... — **no** `400 INVALID_ARGUMENT`.
- If you hit a `429`, you'll see `rate-limited (attempt .../...); retrying in Ns` instead of an instant fail.

**Pass if:** Keyframes generate without the 400 crash.

---

## Test 2: The storyboard appears with a Continue button

**What to do:**
1. Wait for planning to finish (keyframes only — no Veo yet, so it's faster than before).

**Expected:**
- A **Storyboard — N scenes** panel appears in the chat with a horizontal strip of scene cards.
- Each card shows: the keyframe image, a shot-type badge (e.g. CU/MS), camera movement, the scene description, the voiceover script line (in quotes), the SFX note, an **editable subtitle** field, and the duration.
- A blue **"Continue — Render Video"** button sits below the strip.
- **No video has been generated yet.**

**Pass if:** You see the storyboard with per-scene details and a Continue button, before any Veo render.

---

## Test 3: Editing a subtitle then continuing

**What to do:**
1. Change one scene's **Subtitle** field text.
2. Click **Continue — Render Video**.

**Expected:**
- Button shows **"Rendering scenes..."** with a spinner.
- Backend terminal shows `[Orchestrator] Executing Video V2 plan ...`, then per-scene `Submitting Veo clip i`, `Burnt subtitle into scene i`, `Combined N clips with xfade transitions`, and audio merge logs.
- After a few minutes, the finished video appears in the Output Gallery, and your edited subtitle is burnt into that scene.

**Pass if:** Continue renders the video and your subtitle edit is reflected.

---

## Test 4: The final video is multi-scene, localized, with audio

**What to do:**
1. Play the rendered video.

**Expected:**
- Multiple distinct scenes with motion + cross-dissolve transitions.
- Burnt-in subtitles.
- A **Malaysian-localized** voiceover (Bahasa/Manglish) and per-scene sound effects mixed under it.
- Visuals feel Malaysian (local settings, mixed Malay/Chinese/Indian casting where people appear).

**Verify (optional):** Supabase → `generated_ads` → `metadata` has `"generation_method": "veo_multi_scene_v2"`, a `scenes` array with `shot_type`/`camera_movement`/`script`/`sfx`, and a `plan_id`.

**Pass if:** The video is multi-scene, localized, and has voiceover + SFX.

---

## Test 5: Image ads are localized too

**What to do:**
1. Turn Video V2 OFF. Type: `Generate an Instagram image ad for a family nasi lemak restaurant`

**Expected:**
- The image looks Malaysian (local food styling, setting, and if people appear, a natural local mix).

**Pass if:** The image reflects a Malaysian vibe.

---

## Test 6: V2 fails loudly with no Veo (optional)

**What to do:**
1. Unset `VERTEX_PROJECT_ID`, restart, turn V2 ON, generate.

**Expected:**
- Planning fails loudly at the keyframe/plan step or execution reports failed — no fake video.

**Pass if:** Missing Veo config produces a clear failure.

---

## Notes / known limits

- **Two API calls now:** chat produces the plan; Continue posts to `/execute-video-plan`. If you refresh between them, the storyboard is lost (the keyframes are still in S3 under `.../plans/{plan_id}/`, but the UI doesn't reload plans yet). Persisting plans across refresh is a possible follow-up.
- **Cost/quota:** planning uses N image calls; rendering uses N Veo calls. The throttle spaces them to avoid 429s but doesn't eliminate quota limits.

---

## If something fails

Paste the backend terminal lines. Markers:
- Planning: `[VideoAgentV2] Director planned`, `Keyframe i generated`, `Plan {id} ready with N scene(s)`
- Continue: `[Orchestrator] Executing Video V2 plan`, `Submitting Veo clip i`, `Merged audio`
- Rate limits: `Keyframe i rate-limited (attempt .../...)`
