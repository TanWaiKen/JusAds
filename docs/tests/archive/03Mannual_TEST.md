# 03 — Manual Test: Image Reference Strengthening + Video V2 (Multi-Scene Storyboard)

> 🔧 **FIX APPLIED (retest B3–B5):** The Video V2 crash `'bool' object has no attribute 'generate'` was a name clash — the imported module `video_v2` was shadowed by the `video_v2` boolean parameter, so `video_v2.generate` ran on the `True` value. The module is now imported as `video_v2_agent`. **Before retesting: stop the backend, clear cache (`__pycache__`), and restart** so the fix loads.

This round has **two** enhancements. Test them in order.

- **Part A — Image reference strengthening** (quick): when you upload a reference image, the generated image now actually resembles it.
- **Part B — Video V2** (major): a new multi-scene storyboard video pipeline — Director → keyframes → Veo clips → burnt-in subtitles → cross-dissolve transitions → one voiceover.

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

> ⚠️ **No database migration needed** for either part.
> ⚠️ **Video V2 needs Veo:** `VERTEX_PROJECT_ID` must be set in `backend/.env`, GCP credentials valid, and the Veo API enabled. If not, Video V2 will fail loudly (by design — no silent fallback).
> ⚠️ **ffmpeg + ffprobe** must be on PATH (subtitles + transitions use them). Check: `ffmpeg -version` and `ffprobe -version`.
> ⚠️ Clear backend cache if reload misses it: `rmdir /s /q jusads_generation\__pycache__`

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Backend | `jusads_generation/agents/image_agent.py` | `_refine_prompt(..., has_reference)` adds a "build on the reference" clause; generation now leads with an explicit "match the reference" instruction before the reference parts |
| Backend | `jusads_generation/agents/video_v2.py` | **New module** — full multi-scene storyboard pipeline |
| Backend | `jusads_generation/orchestrator.py` | `run_generation(..., video_v2)`; routes video to V2 when enabled |
| Backend | `routes/generation.py` | `ChatRequest.video_v2` flag |
| Frontend | `services/generationApi.ts` | `sendChat`/`streamChat` accept `videoV2` |
| Frontend | `components/workspace/canvas/ChatbotPanel.tsx` | New `videoV2Enabled` prop, passed to `streamChat` |
| Frontend | `components/workspace/canvas/GenerationCanvas.tsx` | New **Video V2 — Multi-Scene** toggle in Settings |

---

# PART A — Image Reference Strengthening

## Test A1: Reference image visibly influences the result

**Feedback**
![alt text](image_014855.jpg)
The shows generated is quite good lah, but also we need localize so need to know the target consumers we ned to addd in settings like got two tab one is target consumers and other is the setting of generation

**What to do:**
1. In the chat footer, click the paperclip (or drag-drop / paste) and upload a clear product image — e.g. a specific bottle, shoe, or snack pack.
2. Type: `Generate an Instagram image ad for this product, bright studio background`
3. Send and wait for the image in the Output Gallery.

**Expected:**
- The generated image clearly resembles the uploaded product — same subject, similar colors and materials — styled into an ad, not a random unrelated image.

**Pass if:** The output looks like *your* product, not a generic stock image.

**Compare (optional):** Generate the same prompt **without** a reference. The referenced one should track your product much more closely.

---

## Test A2: No reference still works (Passed but found other error)

**Feedback**
![alt text](image-2.png)
I dont know but why it refer to the pizza images The primary issue with this image is a mismatch between the visual content and the stated product category. The image displays an iced matcha latte in a cafe setting, while the product being advertised is 'pizza'. This discrepancy can be misleading to consumers and may violate advertising regulations (MY-MCMC-008) which require advertising content to be truthful and not deceptive. While the image itself is culturally appropriate for Malaysia and suitable for platforms like Instagram, TikTok, and Meta, its application as an advertisement for pizza creates a significant contextual problem.

Flagged items
Product in image (matcha latte) does not match advertised product (pizza)
Suggested fix: To achieve compliance and better advertising effectiveness, replace this image with one that prominently features pizza. If the advertisement is for the entire cafe's offerings (including both drinks and pizza), ensure the ad copy clearly communicates this breadth of products. Otherwise, an image of a matcha latte alone is inappropriate for a pizza advertisement.

The image sis correfct but the judges looks to have some issues

**What to do:**
1. Without uploading anything, type: `Generate an image ad for an iced matcha latte`

**Expected:**
- A normal generated matcha image ad. No errors, no crash.

**Pass if:** Reference-free generation behaves exactly as before.

---

# PART B — Video V2 (Multi-Scene Storyboard)

> ⏱️ **Heads-up:** Video V2 is slow. It generates several keyframes and several Veo clips (each Veo clip can take 30s–2min). A 4-scene ad may take several minutes. This is expected.

## Test B1: The Video V2 toggle exists (Passed)

**What to do:**
1. Click the **Settings** gear in the canvas toolbar.

**Expected:**
- Below the **Compliance Check** toggle there is a new **"Video V2 — Multi-Scene"** toggle.
- Off by default. The helper text explains V1 (single clip) vs V2 (storyboard).

**Pass if:** The toggle is visible and starts OFF.

---

## Test B2: V1 video still works (toggle OFF) (Passed)

**What to do:**
1. Leave Video V2 **OFF**.
2. Type: `Generate a TikTok video ad for a new energy drink`
3. Wait for generation.

**Expected:**
- A single Veo video clip appears in the Output Gallery, plays with audio (as before this change).

**Pass if:** The original single-clip video path is unchanged.

---

## Test B3: V2 produces a multi-scene video (toggle ON) (Failed)

**Feedback**
INFO:httpx:HTTP Request: GET https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/platform_rules?select=platform%2Cmedia_type%2Caspect_ratio%2Cmax_duration_seconds%2Cadditional_rules&platform=eq.tiktok&media_type=eq.video&limit=1 "HTTP/2 200 OK"
INFO:jusads_generation.platform_rules:[PlatformRules] Resolved rule for (tiktok, video): aspect_ratio=9:16, max_dimension=1080, max_duration_seconds=180
INFO:jusads_generation.orchestrator:[Orchestrator] Using Video V2 (multi-scene storyboard)
ERROR:jusads_generation.orchestrator:[Orchestrator] video agent crashed: 'bool' object has no attribute 'generate'
INFO:httpx:HTTP Request: POST https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/chat_messages "HTTP/2 201 Created"
INFO:jusads_generation.chat_store:[ChatStore] Persisted assistant turn for task 414c8323-d8bc-496e-9bd1-f2a7b0532340 (message 5f3e6f93-b59a-4344-87a0-45e56d98d6a8)
INFO:jusads_generation.orchestrator:[Orchestrator] Generation run complete (0 ad(s) produced)
INFO:httpx:HTTP Request: PATCH https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/tasks?id=eq.414c8323-d8bc-496e-9bd1-f2a7b0532340&project_id=eq.a8252e1a-e4f2-4184-92aa-28331341c749 "HTTP/2 200 OK"
INFO:agent.supabase_client:Updated task 414c8323-d8bc-496e-9bd1-f2a7b0532340 -> status: completed

Later u it is better u show all the node how the video generated like each scripts each image they can be say as image agent and text agent lah

**What to do:**
1. Open Settings → turn **Video V2 — Multi-Scene** ON → close settings.
2. Type: `Generate a TikTok video ad for a new energy drink, energetic and youthful`
3. Be patient — watch the status line. You should see phases cycle (generating → uploading → compliance if on → completed).

**Expected:**
- After a few minutes, a video appears in the Output Gallery.
- Playing it, you should see:
  - **Multiple distinct scenes** (not one continuous shot), each with motion.
  - **Burnt-in subtitle captions** near the bottom (CapCut-style, white text on a translucent box).
  - **Smooth cross-dissolve transitions** between scenes.
  - **A single voiceover** narrating across the whole ad.

**Pass if:** The video is clearly multi-scene with captions, transitions, and a voiceover.

**Verify in the database (optional):**
- Supabase → `generated_ads` → your row → `metadata` should include `"generation_method": "veo_multi_scene_v2"`, a `scene_count`, and a `scenes` array with descriptions + subtitles.

---

## Test B4: V2 fails loudly if Veo isn't configured (Failed because of the issues above)

**What to do (only if you want to confirm the no-fallback behavior):**
1. Temporarily unset `VERTEX_PROJECT_ID` in `backend/.env` and restart the backend.
2. Turn Video V2 ON and generate a video.

**Expected:**
- The video node reports **failed** (red), and the chat shows an error mentioning Veo / `VERTEX_PROJECT_ID`.
- No silent fake video is produced.

**Pass if:** Missing Veo config produces a clear, loud failure — not a fallback.

> Remember to restore `VERTEX_PROJECT_ID` afterward.

---

## Test B5: Reference image anchors V2 scenes (bonus) (failed because of above)

**What to do:**
1. Upload a product image.
2. Turn Video V2 ON.
3. Type: `Make a short video ad for this product`

**Expected:**
- The scene keyframes (and therefore the clips) feature your product, not an unrelated one.

**Pass if:** Your product appears throughout the generated scenes.

---

## If something fails

Tell me which test number failed and what you saw. Useful checks:
- **Backend terminal** — look for `[VideoAgentV2]` log lines. They trace each phase: `Director planned N scenes`, `Keyframe i generated`, `Submitting Veo clip i`, `Burnt subtitle into scene i`, `Combined N clips with xfade transitions`, `Voiceover merged`.
- **ffmpeg/ffprobe missing** — subtitles/transitions will log warnings and the video may fall back to plain concat (no transitions) or no captions. Install ffmpeg and ensure it's on PATH.
- **Veo errors** — check `VERTEX_PROJECT_ID`, GCP auth, and that the Veo API is enabled/quota available.
- **Very long generation** — normal. Each Veo clip is a separate API call with polling.
