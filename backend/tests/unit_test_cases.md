# JusAds Unit Test Cases

## Main Feature 1 — Compliance Checking Pipeline

The Compliance Pipeline analyzes advertising media (text, image, audio, video) against regulatory and cultural rules for Southeast Asian markets. It follows the flow: **Fetch Rules → Transcribe (audio/video) → AI Analysis → Bias Check → Decision Routing**.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-1.01 | Fetch rules returns valid rules for Malaysia/TikTok | market="malaysia", platform="tiktok", ethnicity="malay", age_group="gen_z" | Rules list is non-empty; persona dict is non-empty; `result["_rules"]` populated | | |
| TC-1.02 | Fetch rules handles empty rule set gracefully | market="unknown_market", platform="unknown_platform" | Returns empty rules list `[]`; logs WARNING; pipeline continues without error | | |
| TC-1.03 | Fetch rules handles Supabase connection failure | Supabase client raises `ConnectionError` | Returns `{"_rules": [], "_persona": {}}`; step recorded as failed in progress tracker | | |
| TC-1.04 | Conditional routing sends audio to transcribe_media | media_type="audio" | `_route_after_fetch` returns `"transcribe_media"` | | |
| TC-1.05 | Conditional routing sends video to transcribe_media | media_type="video" | `_route_after_fetch` returns `"transcribe_media"` | | |
| TC-1.06 | Conditional routing sends text to main_brain_analysis | media_type="text" | `_route_after_fetch` returns `"main_brain_analysis"` | | |
| TC-1.07 | Conditional routing sends image to main_brain_analysis | media_type="image" | `_route_after_fetch` returns `"main_brain_analysis"` | | |
| TC-1.08 | Transcribe media returns valid transcript for audio | media_type="audio", input_path="valid_audio.mp3"; Gemini returns `{"language":"malay","transcript":"hello"}` | `result["_transcript"]` = `{"language":"malay","transcript":"hello"}` | | |
| TC-1.09 | Transcribe media handles Gemini API failure | Gemini raises `Exception("API timeout")` | `result["_transcript"]` = `{"language":"unknown","transcript":"(transcription unavailable)"}` | | |
| TC-1.10 | Main brain analysis — text compliance check | media_type="text", text_input="Buy now! 50% off!", market="malaysia", platform="tiktok"; rules and persona present | Returns result with `risk_percentage` (int), `risk_level` (str), `high_risk_indicator` (list) | | |
| TC-1.11 | Main brain analysis — image compliance check | media_type="image", input_path="test_image.png" (valid file); Gemini returns JSON with risk fields | Returns result with risk_percentage, risk_level, high_risk_indicator; prescan is called first | | |
| TC-1.12 | Main brain analysis — handles missing input file | media_type="image", input_path="nonexistent.png" | Returns result with `error` field; step fails in progress tracker | | |
| TC-1.13 | Main brain analysis — includes business context when available | project has business_profiles entry in Supabase | Prompt sent to Gemini includes company name and product category | | |
| TC-1.14 | Judges agent returns passing evaluation | result contains low-risk compliance analysis | `evaluation["overall_pass"]` = True; `evaluation["hallucination_score"]` >= 5 | | |
| TC-1.15 | Judges agent flags hallucination | result contains fabricated violations not grounded in rules | `result["_hallucination_flagged"]` = True; `evaluation["hallucination_score"]` < 3 | | |
| TC-1.16 | Judges agent handles Gemini failure | Gemini raises Exception during evaluation | `result["_eval_error"]` is set with error message; pipeline continues | | |
| TC-1.17 | Decision router — PASS condition | risk_level="Low", risk_percentage=20, high_risk_indicators=[] | Returns `"pass"` | | |
| TC-1.18 | Decision router — PASS boundary (30%) | risk_level="Low", risk_percentage=30, high_risk_indicators=[] | Returns `"pass"` | | |
| TC-1.19 | Decision router — REMEDIATE for Low risk above threshold | risk_level="Low", risk_percentage=31, high_risk_indicators=["minor issue"] | Returns `"remediate"` | | |
| TC-1.20 | Decision router — CRITICAL_REGEN for Critical risk level | risk_level="Critical", risk_percentage=50, high_risk_indicators=["offensive content"] | Returns `"critical_regen"` | | |
| TC-1.21 | Decision router — CRITICAL_REGEN for high percentage (>85) | risk_level="High", risk_percentage=90, high_risk_indicators=["multiple violations"] | Returns `"critical_regen"` | | |
| TC-1.22 | Decision router — CRITICAL_REGEN boundary (86%) | risk_level="Moderate", risk_percentage=86, high_risk_indicators=["violation"] | Returns `"critical_regen"` | | |
| TC-1.23 | Decision router — REMEDIATE for Moderate risk | risk_level="Moderate", risk_percentage=55, high_risk_indicators=["gender bias"] | Returns `"remediate"` | | |
| TC-1.24 | Decision router — REMEDIATE for High risk below 85% | risk_level="High", risk_percentage=70, high_risk_indicators=["skin exposure"] | Returns `"remediate"` | | |
| TC-1.25 | Decision router — unknown risk_level defaults to REMEDIATE | risk_level="InvalidLevel", risk_percentage=40, high_risk_indicators=[] | Returns `"remediate"`; logs WARNING about unexpected value | | |
| TC-1.26 | Decision router node persists result to Supabase | Valid compliance result with task_id | Supabase `compliance_checks` table updated with status, risk_percentage, result_json | | |
| TC-1.27 | Decision router node queues to FallbackQueue on persistence failure | Supabase update raises Exception | `fallback_queue.enqueue()` called with correct payload; pipeline does not crash | | |
| TC-1.28 | Progress tracker records step start | task_id="test-123", step_name="main_brain_analysis" | `pipeline_progress` table has row with status="running" | | |
| TC-1.29 | Progress tracker records step completion | task_id="test-123", step_name="main_brain_analysis" | Row updated to status="completed" with message | | |
| TC-1.30 | Progress tracker handles Supabase failure silently | Supabase raises Exception during insert | No exception propagated; error logged; pipeline continues | | |

---

## Main Feature 2 — Remediation Pipeline

The Remediation Pipeline fixes non-compliant media assets detected by the Compliance Pipeline. It follows the flow: **Fetch Compliance Result → Confirm Aspect Ratio (human-in-the-loop) → Media-Specific Remediation → Upload & Finalize**.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-2.01 | Fetch compliance result — valid task_id | task_id="existing-task" exists in compliance_checks table | Returns compliance_result, media_type, source_media_url, platform_target; status="remediating" | | |
| TC-2.02 | Fetch compliance result — task_id not found | task_id="nonexistent-task"; Supabase returns empty rows | Returns status="remix_failed"; compliance_result contains error message | | |
| TC-2.03 | Fetch compliance result — Supabase failure | Supabase raises `ConnectionError` | Returns status="remix_failed"; step recorded as failed in tracker | | |
| TC-2.04 | Fetch compliance result — builds remediation plan correctly | compliance_checks record has result_json with high_risk_indicator, suggestion, localization_plan | remediation_plan dict contains all extracted fields | | |
| TC-2.05 | Confirm aspect ratio — skips for text media | media_type="text" | Returns `{"aspect_ratio": ""}` immediately; step logged as "Skipped for text" | | |
| TC-2.06 | Confirm aspect ratio — skips for audio media | media_type="audio" | Returns `{"aspect_ratio": ""}` immediately; step logged as "Skipped for audio" | | |
| TC-2.07 | Confirm aspect ratio — uses default when no platform_rules | media_type="image", platform_target="unknown"; Supabase returns no rules | Returns aspect_ratio="1:1" (image default) | | |
| TC-2.08 | Confirm aspect ratio — video default fallback | media_type="video", platform_target="unknown"; no platform_rules | Returns aspect_ratio="16:9" (video default) | | |
| TC-2.09 | Confirm aspect ratio — interrupt for human confirmation | media_type="image", platform_target="tiktok"; platform_rules has entries | LangGraph `interrupt()` is called with options list; returns user-selected ratio | | |
| TC-2.10 | Confirm aspect ratio — handles Supabase failure | platform_rules query raises Exception | Returns status="remix_failed", aspect_ratio="" | | |
| TC-2.11 | Media remediation — routes to image handler | media_type="image", status!="remix_failed" | `_remediate_image()` is called | | |
| TC-2.12 | Media remediation — routes to video handler | media_type="video", status!="remix_failed" | `_remediate_video()` is called | | |
| TC-2.13 | Media remediation — routes to text handler | media_type="text", status!="remix_failed" | `_remediate_text()` is called | | |
| TC-2.14 | Media remediation — routes to audio handler | media_type="audio", status!="remix_failed" | `_remediate_audio()` is called | | |
| TC-2.15 | Media remediation — skips when status already failed | status="remix_failed" | Returns empty dict `{}`; no remediation handler called | | |
| TC-2.16 | Media remediation — unsupported media type | media_type="3d_model" | Returns status="remix_failed"; ValueError logged | | |
| TC-2.17 | Image remediation — inpainting succeeds on first attempt | Gemini Imagen returns valid image; quality_score >= 70 | Returns output_path, strategy="image_inpaint", quality_score >= 70, attempts=1 | | |
| TC-2.18 | Image remediation — retries up to 3 times on low quality | First 2 attempts produce quality < 70; 3rd attempt >= 70 | Returns with attempts=3; quality_score >= 70 | | |
| TC-2.19 | Image remediation — fails after 3 attempts | All 3 attempts raise Exception or quality < 70 | Returns `{"error": "Image inpainting failed after 3 attempts: ..."}` | | |
| TC-2.20 | Image remediation — full mask fallback when no segmentation | No segmentation or mask_path available | Creates full-image mask (all white); inpainting proceeds | | |
| TC-2.21 | Text remediation — successful rewrite | compliance_result has original_text; Gemini returns valid JSON rewrite | Returns output_path (.txt file), strategy="text_rewrite", rewritten_text populated | | |
| TC-2.22 | Text remediation — no original text available | compliance_result missing both original_text and text_input | Returns `{"error": "No original text found..."}` | | |
| TC-2.23 | Text remediation — Gemini API failure | Gemini raises Exception during rewrite | Returns `{"error": "Text rewrite failed: ..."}` | | |
| TC-2.24 | Audio remediation — ElevenLabs TTS succeeds | ElevenLabs returns audio chunks; DEFAULT_VOICE configured | Returns output_path (.mp3), strategy="audio_tts", voice_id set | | |
| TC-2.25 | Audio remediation — ElevenLabs failure | ElevenLabs raises Exception | Returns `{"error": "Audio TTS remediation failed: ..."}` | | |
| TC-2.26 | Video remediation — no violations timeline | violations_timeline=[] | Returns output_path (original video), strategy="video_i2v", note="no violations to fix" | | |
| TC-2.27 | Video remediation — extracts keyframe via ffmpeg | violations_timeline has entries with start_seconds | ffmpeg command executed to extract keyframe; returns output_path | | |
| TC-2.28 | Upload and finalize — successful S3 upload | remediated_paths has valid file path; S3 upload succeeds | Returns status="remediated"; Supabase updated with s3_remix_key | | |
| TC-2.29 | Upload and finalize — no remediated paths | remediated_paths=[] | Returns status="remix_failed"; step fails in tracker | | |
| TC-2.30 | Upload and finalize — S3 upload failure | `upload_file_public` raises Exception | Returns status="remix_failed"; Supabase status set to "remix_failed" | | |
| TC-2.31 | Upload and finalize — skips when already failed | status="remix_failed" from previous step | Returns empty dict `{}`; no upload attempted | | |
| TC-2.32 | Upload and finalize — Supabase update failure after S3 success | S3 upload OK but Supabase update raises Exception | Returns status="remix_failed"; error logged | | |
| TC-2.33 | Image quality check — blank image scored low | Edited image is nearly all white (std_dev < 5) | Returns score = 10 | | |
| TC-2.34 | Image quality check — reasonable image scored high | Edited image has good variation and low pixel difference from original | Returns score >= 50 | | |
| TC-2.35 | Pipeline runner — streams node events and tracks progress | Valid compliance state provided | Each node emits start_step and complete_step; final_state returned | | |
| TC-2.36 | Pipeline runner — handles GraphInterrupt | Pipeline hits `interrupt()` in confirm_aspect_ratio | Returns None; tracker records human_review step as running | | |
| TC-2.37 | Pipeline runner — resume after human decision | `resume()` called with decision="9:16" | Pipeline continues from interrupt; final_state returned | | |
| TC-2.38 | Pipeline runner — timeout on human decision | `run_with_human_loop()` with timeout=0.1; no decision arrives | Returns None; tracker records "Human review timed out" | | |
| TC-2.39 | Binary mask generation from segmented overlay | Original image and segmented overlay with painted regions | Binary mask has white (255) where overlay differs; black (0) elsewhere | | |
| TC-2.40 | S3 key building for remediated assets | asset_type="remixed", username="pipeline", project_id, task_id, filename | Returns properly formatted S3 key path | | |

---

---

## Main Feature 3 — Ad Generation Pipeline

The Ad Generation Pipeline is an agentic multi-modal ad creator. It detects what media types the user wants, resolves platform-specific sizing rules, fans out to independent media agents (text, image, audio, video), bridges each ad to compliance, and persists results. It uses LangGraph orchestration with SSE streaming.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-3.01 | Intent detection — explicit video request | user_message="Generate a TikTok video ad for my coffee" | Returns `["video"]` | | |
| TC-3.02 | Intent detection — multiple media types | user_message="Create image and text ads for shoes" | Returns `["text", "image"]` | | |
| TC-3.03 | Intent detection — no media type detected | user_message="I want to promote my restaurant" | Returns `[]` (empty list) | | |
| TC-3.04 | Intent detection — casual chat (no generation intent) | user_message="Hi, how are you?" | Returns `[]` | | |
| TC-3.05 | Intent detection — keyword fallback when Gemini fails | Gemini raises Exception; user_message="Make me a poster" | Falls back to keyword classifier; returns `["image"]` | | |
| TC-3.06 | Intent detection — action word required for keyword classifier | user_message="coffee shop poster ideas" (no action word) | Returns `[]` unless "poster" triggers explicit media check | | |
| TC-3.07 | Intent detection — empty message | user_message="" | Returns `[]` | | |
| TC-3.08 | Platform normalization — default to Instagram | target_platform=None | Returns `"instagram"` | | |
| TC-3.09 | Platform normalization — valid TikTok | target_platform="TikTok" | Returns `"tiktok"` (lowercase) | | |
| TC-3.10 | Platform normalization — unsupported platform rejected | target_platform="facebook" | Raises `UnsupportedPlatformError` | | |
| TC-3.11 | Platform normalization — empty string defaults | target_platform="" | Returns `"instagram"` | | |
| TC-3.12 | Platform rule resolution — valid combination | platform="instagram", media_type="image" | Returns `PlatformRule` with aspect_ratio, max_dimension | | |
| TC-3.13 | Platform rule resolution — missing rule | platform="shopee", media_type="audio" (no rule exists) | Raises `MissingRuleError` | | |
| TC-3.14 | Platform rule resolution — Supabase failure | Supabase raises Exception | Raises `MissingRuleError` (wraps the original exception) | | |
| TC-3.15 | Chat store — persist user turn | project_id, task_id, role="user", content="Make me a poster" | Row inserted in `chat_messages` table; returns row with `id` | | |
| TC-3.16 | Chat store — content truncation at 10,000 chars | content length = 15,000 characters | Content truncated to 10,000 chars; WARNING logged | | |
| TC-3.17 | Chat store — persistence failure queues to fallback | Supabase insert fails | Raises `ChatPersistenceError`; payload enqueued in `fallback_queue` | | |
| TC-3.18 | Chat store — list recent messages (limit 20) | task has 30 messages in DB | Returns last 20 messages ordered oldest→newest | | |
| TC-3.19 | Chat store — empty history returns empty list | task has no messages | Returns `[]` without raising | | |
| TC-3.20 | Orchestrator — clarification when no media detected | detected media types = [] | SSE emits clarification message; no agent invoked | | |
| TC-3.21 | Orchestrator — fan-out to detected agents | detected = ["text", "image"] | text_node and image_node execute in parallel; video/audio nodes skipped | | |
| TC-3.22 | Orchestrator — failing agent doesn't block siblings | image_agent raises Exception; text_agent succeeds | text ad produced; image ad marked as failed; no crash | | |
| TC-3.23 | Orchestrator — missing rule rejects single media type | No rule for (tiktok, audio) | Audio generation skipped with "failed" event; other media types proceed | | |
| TC-3.24 | Orchestrator — brief enrichment with product context | product_name="Tiger Sugar", product_category="food_beverage" | Enriched brief includes "[SETTINGS: Product/Brand: Tiger Sugar | Category: food and beverage]" | | |
| TC-3.25 | Orchestrator — pipeline state building | 2 generated ads (text + image) | pipeline_state has nodes for input, text, image, output with edges connecting them | | |
| TC-3.26 | Orchestrator — SSE status events emitted per node | Generation runs for image media type | SSE events: `{node:"image", status:"in-progress"}` → `{node:"image", status:"completed"}` | | |
| TC-3.27 | Compliance bridge — pass verdict maps to final-compliant | Pipeline returns status="pass" | `_map_verdict` returns `"final-compliant"` | | |
| TC-3.28 | Compliance bridge — remediate verdict maps to non-compliant | Pipeline returns status="remediate" | `_map_verdict` returns `"final-non-compliant"` | | |
| TC-3.29 | Compliance bridge — timeout maps to non-final | Pipeline exceeds 120s timeout | Returns compliance_status="non-final", error mentions timeout | | |
| TC-3.30 | Compliance bridge — skips incomplete ad | ad status="failed" (generation didn't complete) | Returns non-final immediately; no pipeline invoked | | |
| TC-3.31 | Compliance bridge — media download failure | S3 download raises Exception | Returns non-final with error "media download failed" | | |
| TC-3.32 | Compliance bridge — summarize_reasons extracts key fields | compliance_result has risk_level, risk_percentage, high_risk_indicator, suggestion | Returns compact dict with only those fields populated | | |
| TC-3.33 | Compliance bridge — summarize_reasons handles empty/non-dict | compliance_result=None or compliance_result="string" | Returns empty dict `{}` | | |
| TC-3.34 | Generation route — task not found returns 404 | project_id and task_id don't match any task | Returns HTTP 404 `{"error": "Task not found"}` | | |
| TC-3.35 | Generation route — store unavailable returns 503 | _store is None (Supabase not initialized) | Returns HTTP 503 `{"error": "Persistence store is unavailable"}` | | |

---

## Main Feature 4 — Ad Publishing (Human-in-the-Loop Gate)

The publishing feature is the human approval gate that controls whether generated ads can be distributed. Only ads that pass compliance review can be published. Publishing is idempotent and blocks non-compliant creative.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-4.01 | Publish ad — successful approval | ad exists with status="completed", compliance_status="non-final" | Returns `{ad_id, status:"published", already_published:False}` | | |
| TC-4.02 | Publish ad — already published (idempotent) | ad exists with status="published" | Returns `{ad_id, status:"published", already_published:True}` | | |
| TC-4.03 | Publish ad — blocked by compliance failure | ad has compliance_status="final-non-compliant" | Raises `CompliancePublishBlockedError` | | |
| TC-4.04 | Publish ad — ad not found | ad_id doesn't exist for the given project_id | Raises `AdNotFoundError` | | |
| TC-4.05 | Publish ad — Supabase read failure | Supabase raises Exception during ad lookup | Raises `PublishError` with "persistence store unavailable" | | |
| TC-4.06 | Publish ad — Supabase update failure | Ad exists but status update fails | Raises `PublishError` with "failed to update ad status" | | |
| TC-4.07 | Publish ad — draft status can be published | ad has status="draft" | Publishes successfully; status flipped to "published" | | |
| TC-4.08 | Publish ad — sets updated_at timestamp | ad published successfully | `updated_at` field set to current UTC time in ISO format | | |
| TC-4.09 | Publish route — returns 404 for missing ad | POST /publish with non-existent ad_id | HTTP 404 response | | |
| TC-4.10 | Publish route — returns 409 for compliance block | POST /publish for non-compliant ad | HTTP 409 response with compliance error | | |

---

## Main Feature 5 — Ad Distribution (Social Platform Posting)

The distribution feature pushes published ads to social platforms (TikTok, Instagram, YouTube) via the Zernio SDK. It includes account resolution, post creation, recording distribution metadata, and analytics retrieval.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-5.01 | Distribute ad — successful TikTok post | ad_id exists, platform="tiktok", ZERNIO_API_KEY set, ZERNIO_ACCOUNT_TIKTOK set | Returns `{post_id, status:"distributed", platform:"tiktok"}` | | |
| TC-5.02 | Distribute ad — missing API key | ZERNIO_API_KEY="" (empty) | Raises `DistributionError` with "ZERNIO_API_KEY is not configured" | | |
| TC-5.03 | Distribute ad — unconfigured platform account | platform="invalid-platform"; no account mapping | Raises `AccountNotConfiguredError` | | |
| TC-5.04 | Distribute ad — Zernio SDK failure | Zernio client raises Exception during posts.create | Raises `DistributionError` wrapping the original | | |
| TC-5.05 | Distribute ad — records distribution metadata on success | Distribution succeeds | `generated_ads` row updated with distributed_at, distribution_platform, distribution_post_id | | |
| TC-5.06 | Distribute ad — metadata persistence failure is non-fatal | Distribution succeeds but Supabase update fails | Returns success result; logs WARNING (doesn't raise) | | |
| TC-5.07 | Account resolution — TikTok maps to configured ID | platform="tiktok" | Returns ZERNIO_ACCOUNT_TIKTOK value | | |
| TC-5.08 | Account resolution — Instagram maps to configured ID | platform="instagram" | Returns ZERNIO_ACCOUNT_INSTAGRAM value | | |
| TC-5.09 | Account resolution — unknown platform returns None | platform="snapchat" | Returns `None` | | |
| TC-5.10 | Distribution route — ad not published returns 409 | ad has status="completed" (not "published") | HTTP 409 "Ad must be published before distributing" | | |
| TC-5.11 | Distribution route — ad has no media URL returns 409 | ad metadata has no s3_url | HTTP 409 "Ad has no public media URL to distribute" | | |
| TC-5.12 | Get analytics — ad not distributed (draft) | Ad has no distribution_post_id | Returns `{status:"draft", metrics: all zeros}` | | |
| TC-5.13 | Get analytics — Zernio API key missing (mock fallback) | ZERNIO_API_KEY="" but ad is distributed | Returns `{status:"mocked"}` with generated engagement data | | |
| TC-5.14 | Get analytics — successful real analytics | ZERNIO_API_KEY set; analytics.get_analytics returns data | Returns `{status:"active"}` with real metrics and chart_data (7 days) | | |
| TC-5.15 | Get analytics — ad not found | ad_id doesn't exist for project_id | Returns mock analytics as fallback (error caught) | | |

---

## Main Feature 6 — CapCut Draft Export

The CapCut Draft Export feature generates importable CapCut/JianYing project drafts with video + image overlay + transitions. Users can download a ZIP or auto-install to their local CapCut app.

| TC-No | Description | Input Conditions | Expected Output | Actual Output | Status |
|-------|-------------|------------------|-----------------|---------------|--------|
| TC-6.01 | CapCut status check — library available | pycapcut is installed | Returns `{available:True, library:"pycapcut"}` | | |
| TC-6.02 | CapCut status check — library unavailable | Neither pycapcut nor pyJianYingDraft installed | Returns `{available:False, library:null}` | | |
| TC-6.03 | Generate draft — library not available returns 503 | CAPCUT_AVAILABLE=False | HTTP 503 with "Install pycapcut" message | | |
| TC-6.04 | Generate draft — successful creation | Valid video + image uploaded; pycapcut available | Returns `{success:True, download_url, draft_name, video_duration_sec, canvas}` | | |
| TC-6.05 | Generate draft — invalid video file | Uploaded file is not a valid video (e.g., text file renamed to .mp4) | Returns HTTP 500 with error details | | |
| TC-6.06 | Generate draft from local — test assets exist | Test Video.mp4 and Boba Infographic.jpg present in assets | Draft created successfully using local files | | |
| TC-6.07 | Generate draft from local — video not found | Test Video.mp4 missing from assets directory | HTTP 404 "Test video not found" | | |
| TC-6.08 | Generate draft from local — image not found | Boba Infographic.jpg missing from assets directory | HTTP 404 "Test image not found" | | |
| TC-6.09 | Media duration detection — valid video | Valid .mp4 file with known duration | Returns duration in seconds (float > 0) | | |
| TC-6.10 | Media duration detection — ffprobe unavailable | ffprobe not in PATH | Returns `None` (graceful fallback) | | |
| TC-6.11 | Download draft — draft exists | draft_name matches an existing generated draft | Returns ZIP FileResponse with correct content-type | | |
| TC-6.12 | Download draft — draft not found | draft_name doesn't match any generated draft | HTTP 404 "Draft not found" | | |
| TC-6.13 | Draft files endpoint — returns JSON content | Valid draft with .json files | Returns dict of filename→content pairs for all JSON files | | |
| TC-6.14 | Draft files endpoint — no JSON files | Draft folder exists but contains no .json files | HTTP 404 "No draft files found" | | |
| TC-6.15 | Install to CapCut — folder found | CapCut Drafts folder exists on system | Draft copied to CapCut folder; returns `{success:True, installed_path}` | | |
| TC-6.16 | Install to CapCut — CapCut not installed | No CapCut Drafts folder on system | HTTP 404 "CapCut Drafts folder not found" | | |
| TC-6.17 | Install to CapCut — draft not generated | draft_name doesn't exist in temp drafts | HTTP 404 "Draft not found. Generate it first." | | |
| TC-6.18 | Find CapCut drafts folder — Windows detection | Running on Windows with CapCut installed at standard path | Returns full path to `com.lveditor.draft` folder | | |
| TC-6.19 | Find CapCut drafts folder — not installed | CapCut not installed on system | Returns `None` | | |
| TC-6.20 | Transition types — fade transition applied | transition_type="fade" | Draft created with fade transition between video segments | | |

---

## Legend

| Status | Meaning |
|--------|---------|
| PASS | Test executed successfully, actual output matches expected output |
| FAIL | Test executed but actual output differs from expected output |
| BLOCKED | Test cannot be executed due to environmental/dependency issue |
| NOT RUN | Test has not been executed yet |
