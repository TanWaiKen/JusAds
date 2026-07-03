# Enhancement Tasks — Remaining Phases

Status: `[ ]` = pending · `[x]` = done · `[~]` = in progress

---

## Phase A: Wire Settings Into Generation

All settings fields now exist in the UI but only `targetEthnicity` and `targetPlatform` reach the backend. This phase sends everything and makes the AI use it.

- [x] A1 — Add `age_group`, `market`, `language`, `product_name`, `product_category`, `gender` to `ChatRequest` body + `sendChat`/`streamChat` frontend
- [x] A2 — Backend `run_generation` receives them and passes to Director/agent prompts (Gen Z → slang, Baby Boomer → formal Bahasa, etc.)
- [x] A3 — Wire `gender` to voice selection (currently hardcoded female)
- [x] A4 — Wire `market` to compliance bridge (currently hardcoded "malaysia")
- [x] A5 — Wire `language` to voiceover TTS `language_code` and copy/subtitle generation

---

## Phase B: Persist Results Across Refresh

The biggest recurring feedback — generated ads, published status, and the storyboard plan all vanish on page reload.

- [x] B1 — On task page load, fetch `generated_ads` from Supabase for that task and repopulate the Output Gallery
- [x] B2 — Show published status on reload (read `status` column, not just in-session state)
- [x] B3 — Persist the `video_plan` (storyboard) so it survives refresh before Continue is clicked
- [x] B4 — Persist settings per-project in Supabase so they don't reset on refresh

---

## Phase C: Compliance Accuracy

Fix the compliance "pizza vs matcha" hallucination and make compliant ads explain themselves.

- [x] C1 — Pass `product_name` + `product_category` to compliance pipeline as context (fixes judge hallucinating wrong product)
- [x] C2 — Ensure compliant ads return their low-risk reasoning (check why `explanation` is empty on pass)

---

## Phase D: Distribution (Zernio Integration)

Wire real publishing to social platforms via the Zernio unified API.

- [x] D1 — Create `backend/jusads_generation/distribution.py` — calls Zernio `POST /api/v1/posts` with the ad's S3 public URL
- [x] D2 — After publish, show a "Distribute" button that triggers distribution to the configured platform (route + UI button done)
- [x] D3 — Support TikTok + Instagram via the unified Zernio endpoint (platform from settings)
- [x] D4 — Record distribution status on the `generated_ads` row (distributed_at, distribution_platform, distribution_post_id)

---

## Phase E: UX Enhancements

- [x] E1 — Video V2 node breakdown: show each scene as a canvas node (keyframe image + text agent per scene)
- [x] E2 — Prompt template form fields (fill-in-the-blank cards instead of raw `[placeholder]` text)
- [ ] E3 — Folder cleanup: consolidate shared utils/clients from `backend/agent/` and `backend/jusads_generation/`

---

## Phase F: Prompt Vector Database (Embedding Search)

Use the `nano-banana-pro-prompts` CSV with embeddings (Supabase pgvector or Qdrant) to find the best matching prompt template based on user input. Powers smarter prompt suggestions and the prompt library.

- [x] F1 — Ingest the prompts CSV into a vector table (pgvector on Supabase or Qdrant collection)
- [x] F2 — Build a similarity-search endpoint: `GET /api/prompt-suggestions?query=...` returns top-K matching templates
- [x] F3 — Wire the Prompt Library UI to query the search endpoint and show relevant templates ranked by similarity
- [x] F4 — Auto-suggest: as the user types in the chat input, show inline prompt suggestions from the vector DB


---

## Phase R: Intelligent Remediation Engine (§ 13)

AI-driven tool routing for compliance remediation. The AI classifies violation severity and picks the cheapest/fastest tool.

- [x] R1.1 — AI Tool Router (`jusads_compliance/tool_router.py`) — Gemini classifies severity + picks tools from 16-tool catalog
- [x] R1.2 — Heuristic fallback routing (when Gemini unavailable) — deterministic risk% thresholds
- [x] R1.3 — CapCut client (`jusads_compliance/capcut_client.py`) — HTTP API mode + FFmpeg fallback (text overlay, trim, speed ramp, transition, audio replace, scene replace)
- [x] R1.4 — Voice Clone Manager (`jusads_compliance/voice_clone_manager.py`) — persistent brand voice via ElevenLabs, dub_segment, full_reread
- [x] R1.5 — Remediation Executor (`jusads_compliance/remediation_executor.py`) — orchestrates tool execution from routing decision
- [x] R1.6 — API endpoints: `POST /smart-remediate` (SSE), `GET /routing-preview`, `POST /clone-voice`
- [x] R1.7 — Database migration `018_brand_voices_table.sql` (brand_voices table + remediation_metadata column)
- [x] R1.8 — Manual test document (`docs/tests/11Mannual_TEST.md`)
- [ ] R2 — Per-segment dubbing with timeline sync (replace specific violation timestamps in audio)
- [ ] R3 — Full CapCut API integration when self-hosted server is deployed (text animations, effects, stickers)
- [ ] R4 — Frontend UI: before/after comparison view with tool badges + confidence meter
