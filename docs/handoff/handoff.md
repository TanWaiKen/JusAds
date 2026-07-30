# JusAds Handoff

**Date:** 26 July 2026  
**Branch:** `main`  
**Working tree:** Uncommitted implementation changes; no commit or push was made during the latest work.

## Delivered in this work session

### V3-only localized video generation
- V3 Grid is the only supported video renderer; incomplete/non-V3 plans are rejected before paid rendering.
- Localized creative strategies support fast, dense delivery and forbid slow-motion padding, generic lifestyle montage, slow establishing openings, and logo-only openings.
- V3 output persistence now keeps canonical S3 object keys separately from public preview URLs.
- A final render must persist an MP4 and generated-ad row before the backend marks a V3 plan rendered.
- `v3_rendered_plan_id` is retained in the task pipeline state so the storyboard remains available for rerenders without trapping Easy Mode on the approval page.

### Easy Mode results
- After a completed V3 render, Easy Results now prioritizes the final output gallery over the retained storyboard.
- The client treats failed SSE events and missing persisted final videos as failures; it no longer reports success just because an SSE stream closes.
- The storyboard explains why rendering is disabled: missing scripts/captions/keyframes, duration or budget issues, or unconfirmed facts/localization.

### Asset library and downloads
- Uploaded references are inserted into `generated_ads` only after their direct S3 upload succeeds.
- Assets distinguishes output and reference roles and hides V3 intermediate artifacts.
- The Assets page supports separate View and Download actions for generated and uploaded assets.
- Downloads use asset ID plus project owner validation before a short-lived attachment-style S3 URL is generated.
- Text-only generated ads download locally as `.txt` because they do not have an S3 object.

### YouTube Shorts hook discovery
- `backend/shared/youtube_client.py` provides the reusable YouTube Data API client.
- `backend/jusads_generation/hook_search.py` filters to Shorts (`<=60s`), applies hook taxonomy/market queries, and records lightweight preference signals.
- Hook API endpoints: `POST /api/hook-search`, `POST /api/hook-search/preference`, `GET /api/hook-search/tags`.
- Advanced Mode has a YouTube Shorts hook-reference panel. References guide style/energy/pacing only; they are not copied as footage.

### Audio and localized scripts
- ElevenLabs V3 is primary for expressive scene-level delivery tags; Multilingual v2 remains a reliability fallback.
- Audio planning localizes language and maintains clean captions separately from tag-bearing planned scripts.
- Campaign Output no longer duplicates Audio Agent playback/download UI.

### Today’s Idea
- Misdated 11.11/Double 11 events are rejected unless they occur on 11 November; equivalent 12.12 validation is also enforced.
- Stale Double 11 daily-idea cache payloads are rejected outside their 21-day lead-up window.
- Same-day event wording says the event is happening today instead of “begins in 0 days.”
- The daily-idea payload version is `2`, forcing older cached wording to regenerate.
- Easy Mode renders the complete idea payload as a visual brief: creative direction, opening hook, format/event context, timed execution plan, and sources.
- The detailed brief is collapsible with an accessible **View brief / Hide brief** toggle.

## Active integration map

| Area | Primary files |
|---|---|
| V3 planning/rendering | `backend/jusads_generation/agents/video_v3_grid.py`, `backend/jusads_generation/orchestrator.py`, `backend/routes/generation.py` |
| S3 uploads/downloads | `backend/routes/files.py`, `backend/shared/s3_client.py`, `frontend/src/services/fileService.ts` |
| Easy generation/results | `frontend/src/pages/easy-generation.tsx`, `frontend/src/pages/easy-results.tsx`, `frontend/src/components/workspace/canvas/VideoPlanStoryboard.tsx` |
| Asset library | `frontend/src/pages/assets.tsx`, `backend/routes/generation.py` (`GET /api/user-assets`) |
| Daily creative idea | `backend/jusads_trends/daily_idea.py`, `backend/routes/trends.py`, `frontend/src/services/trendsApi.ts` |
| Hook search | `backend/shared/youtube_client.py`, `backend/jusads_generation/hook_search.py`, `frontend/src/components/workspace/canvas/HookSearchPanel.tsx`, `frontend/src/services/hookSearchApi.ts` |

Frontend routes are registered in `frontend/src/App.tsx`; backend generation/files routes are registered by `backend/app.py`.

## Prerequisites

- Do not expose or commit backend `.env` values.
- YouTube hook search requires the configured YouTube Data API credential and `backend/migrations/025_hook_preferences.sql` for persisted preference learning.
- Existing asset/download behavior requires the `generated_ads.asset_role` schema from migration 021 and project owner records in Supabase.
- Daily ideas use saved cultural events/trend data. Invalid cached payloads are ignored, but source event data should still be corrected at the source.

## Validation completed

- Frontend `npm run build`: passed after Easy Results, Assets, daily-idea, and brief-toggle updates.
- Backend targeted tests: `tests/test_video_audio_design.py` + `tests/test_guided_prompts.py` — **9 passed**.
- Daily idea tests: `tests/test_daily_idea.py` — **5 passed**.
- Python compilation and diagnostics on the changed backend/frontend files: passed.
- Live `GET /api/trends/daily-idea?market=malaysia` check: stale Double 11 response was removed; it returns payload version 2 and complete brief fields.

## Current uncommitted source changes

```
backend/jusads_generation/agents/video_v3_grid.py
backend/jusads_generation/orchestrator.py
backend/jusads_trends/daily_idea.py
backend/routes/files.py
backend/routes/generation.py
backend/shared/s3_client.py
frontend/src/components/workspace/canvas/InspectorPanel.tsx
frontend/src/components/workspace/canvas/VideoPlanStoryboard.tsx
frontend/src/pages/assets.tsx
frontend/src/pages/easy-generation.tsx
frontend/src/pages/easy-results.tsx
frontend/src/services/fileService.ts
frontend/src/services/statisticsApi.ts
frontend/src/services/trendsApi.ts
```

## Cleanup performed

Removed verified generated/manual-test artifacts that were not used by the application:

- `.playwright-mcp/` browser snapshots, console logs, screenshots, and capture video
- root test screenshots: `advanced_mode_audio_ad_canvas.png`, `easy_mode_audio_ad_form.png`, `real_project_advanced_canvas.png`, `real_project_audio_ad_form.png`
- `output.bin`
- exported work-session transcript: `Good point  reference nodes are either in or o.md`

The root `.pytest_cache/` could not be removed because Windows had it locked; it is already ignored by Git and can be deleted after the locking process exits.

### Database Schema Cleanup

The database schema was heavily consolidated (via migration `029_cleanup_and_merge_tables.sql` and `027_private_media_key_canonicalization.sql`) to remove unused features and legacy structures:

- **Merged / Canonicalized**: 
  - `creative_trend_sources` table was merged into the `creative_trend_signals.evidence_urls` (`jsonb`) column to reduce joins.
  - `brand_voices.sample_url` was superseded by `brand_voices.sample_s3_key`.
  - All Media URL columns (e.g., `s3`, `asset`, `clip` keys across `business_profiles`, `compliance_checks`, `violations`, `generated_ads`, `brand_voices`) were canonicalized to store **only the S3 object key**, never the full public URL. The backend generates short-lived presigned URLs at response time.
- **Dropped Tables**:
  - The following tables were removed (`DROP TABLE ... CASCADE`) because their features were either deprecated, replaced by new architectures, or never fully integrated into the live application: `creative_trend_sources`, `tavily_usage_log`, `compliance_evaluations`, `remediation_recheck_jobs`, `remediation_versions`, `private_media_url_audit`, `pipeline_progress`, `storyboard_scenes`, `post_statistics_cache`, and `remediation_logs`.

### Deliberately retained, pending owner decision

- `README (1).md`: reference/API documentation
- `design.md`: product/design guidance
- `assets/Gen5/`: manual/sample creative input
- `Hook Guidance.mp4`: existing media reference

These are untracked but are not proven generated or unused. Archive/remove them only if their owner confirms they are no longer needed.

## Remaining follow-up

### 1. ~~Dead API endpoint removal (19 endpoints)~~ ✅ DONE

Removed 19 dead backend routes across 4 files. Cleaned up orphaned imports. All tests pass.

**Compliance — dead routes** (in `backend/routes/compliance.py`):
- `POST /api/compliance/{task_id}/remediate` — replaced by `/remix`
- `POST /api/compliance/{task_id}/smart-remediate` — experimental AI tool router, never shipped
- `GET /api/compliance/{task_id}/routing-preview` — preview of smart-remediate
- `GET /api/compliance/history` — old per-username history, replaced by project/task structure

### 2. ~~Fix YouTube Hook Reference Cache and Queries~~ ✅ DONE

- Bypassed RLS for `youtube_hook_reference_cache` and `hook_preferences` by providing new SQL without `ENABLE ROW LEVEL SECURITY`. This allows the backend to cache requests successfully.
- Replaced static string concatenation in `youtube_hook_cache.py` with an LLM call to `gemini-2.5-flash` (via `SMALL_TEXT_MODEL`) to generate effective, highly-optimized 4-word YouTube search queries. 
- Updated `youtube_hook_references.py` to run the AI query generation in `asyncio.to_thread()` to prevent freezing the FastAPI event loop.
- Updated `backend/shared/config.py` to properly use `"gemini-2.5-flash"` for `SMALL_TEXT_MODEL` without conflicting with `LLM_MODEL_ID`.

- `GET /api/media/{task_id}/{asset_type}` — old presigned URL, replaced by `/api/files/download-url`
- `GET /api/compliance/{task_id}/progress` — old polling, replaced by SSE streaming in `/check`

**Generation — dead routes** (in `backend/routes/generation.py`):
- `GET /api/projects/{project_id}/checks` — old "checks" concept, replaced by tasks
- `GET /.../ads/{ad_id}/analytics` — per-ad analytics stub, never built in UI
- `POST /.../tasks/{task_id}/upload-url` — task-scoped upload, replaced by `/api/files/upload-url`
- `POST /.../tasks/{task_id}/upload` — server-side fallback upload, frontend uses direct-to-S3
- `GET /api/guided-form-schema` — dynamic form schema, frontend hardcodes the form

**CapCut — entire module dead** (in `backend/routes/capcut_draft.py`):
- `GET /api/capcut/status`, `POST /api/capcut/generate-draft`, `POST /api/capcut/generate-draft-local`, `POST /api/capcut/generate-draft-from-url`, `GET /api/capcut/download/{name}`, `GET /api/capcut/draft-files/{name}`, `GET /api/capcut/instructions`, `POST /api/capcut/install-to-capcut/{name}`, `POST /api/capcut/generate-dual`

**Progress — dead file** (`backend/routes/progress.py`):
- Remove entirely; progress polling is replaced by SSE.

### 2. Endpoint renames for cleaner namespacing

| Current | Proposed | Reason |
|---------|----------|--------|
| `GET /api/prompt-suggestions` | `GET /api/prompts/search` | Group under `/prompts/` |
| `GET /api/prompt-recommendations` | `GET /api/prompts/recommend` | Group under `/prompts/` |
| `GET /api/user-assets` | `GET /api/assets` | User is implied from auth |
| `POST /api/hook-search` | `POST /api/hooks/search` | Group under `/hooks/` |
| `POST /api/hook-search/preference` | `POST /api/hooks/preference` | Group under `/hooks/` |
| `GET /api/hook-search/tags` | `GET /api/hooks/tags` | Group under `/hooks/` |
| `GET /api/distribution/accounts` | `GET /api/social/accounts` | Group with statistics under `/social/` |
| `GET /api/statistics/posts` | `GET /api/social/statistics` | Group with distribution under `/social/` |

Update both backend route registrations and all frontend service callers in lockstep.

### 3. Hook search frontend integration

The backend hook search endpoints (`/api/hook-search`, `/api/hook-search/preference`, `/api/hook-search/tags`) and the frontend service layer (`hookSearchApi.ts`) and panel (`HookSearchPanel.tsx`) are built but need end-to-end wiring:
- Confirm the backend server reloads with the new `hook_search.py` and `youtube_client.py` modules.
- Test live YouTube Shorts search from the Settings panel in Advanced Mode.
- Wire selected hook video references into the generation chat context.
- Run the Supabase migration `025_hook_preferences.sql` for preference persistence.

### 4. Voice clone integration into remix flow

`POST /api/compliance/{task_id}/clone-voice` is kept but not yet connected to the frontend. Integration plan:
- Add a "Retain original voice?" toggle in the remix UI when remediating audio/video.
- Flow: ElevenLabs voice isolation → extract speaker identity → TTS with cloned voice profile.
- Wire into the existing `/remix` SSE stream as a remediation option.

### 5. Audio ads — verify sound output

- Run an audio-only generation via Easy Mode (`design_type: "audio_ad"`) and confirm the output `.mp3` has audible VO + SFX.
- Known weakness: if every scene TTS fails, `_concat_scenes()` returns `None` but the ad is still marked `completed`. Verify the actual S3 object, not just the DB status.

### 6. V3 video audio — diagnose silent video

The V3 final video may be assembled without sound. Likely causes (priority order):
1. `audio_program_path` is absent → FFmpeg runs with `-an` (mute fallback).
2. ElevenLabs TTS/music/SFX all fail → no program audio built.
3. `native_omni` mode preserves only Gemini Omni audio, which may be silent.
4. FFmpeg `_mix_audio()` fails on corrupt/unsupported audio → copies video without audio.

Diagnosis: check `voiceover_type`, ElevenLabs SSE statuses, existence of `vo_*.mp3` / `music_*.mp3` / `audio_program_*.m4a`, and run `ffprobe -show_streams final_video.mp4`.

### 7. Machine learning — hook preference learning enhancement

Current approach uses simple tag-frequency association rules. Potential improvements:
- Collaborative filtering across users with similar market/creative-style profiles.
- Embedding-based similarity (CLIP or YouTube video embeddings) for content-aware recommendations.
- A/B test hook effectiveness by tracking downstream ad performance metrics.
- Feedback loop: which hook references led to higher-performing generated ads.

### 8. Compliance checker enhancements

- Integrate voice clone as a remediation option (see item 4).
- Add platform-specific compliance rules (TikTok vs Instagram vs YouTube Shorts format/duration constraints).
- Auto-detect and flag copyrighted music in uploaded references.
- Severity-based remediation priority (critical blockers vs. recommendations).

### 9. Existing items carried forward

- Run a real Easy Mode V3 render after deployment/restart and verify the result transitions from storyboard to output gallery.
- Manually verify downloads for generated image/video/audio/text plus uploaded image/video/audio references.
- Confirm backend authentication derives identity from Cognito/JWT rather than accepting client-supplied email across all asset/project routes; the current download endpoint validates ownership against the request email but full server-side token verification remains a broader security task.
- Review and either commit or archive the remaining untracked reference documents/sample inputs (`README (1).md`, `design.md`, `assets/Gen5/`, `Hook Guidance.mp4`) before the next commit.
