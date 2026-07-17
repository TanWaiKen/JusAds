# Chapter 4: Design and Implementation

This document contains the implementation details, including the development plan task list (Section 4.5.1) and critical code sections with explanations (Section 4.6), structured for copy-pasting directly into your FYP report.

---

## 4.5.1 Development Plan

To ensure software reliability and smooth debugging, the system architecture was systematically broken down into distinct functional modules. This allowed the developer to decouple complex computational intelligence tasks from standard frontend document manipulation and user experience rendering. Managing the implementation through targeted feature checklist clusters proved to be highly effective for the development process. 

Below is the structured step-by-step development checklist designed to guide the replication or rebuilding of the JusAds AI-powered advertising compliance platform.

---

### 1) CORE INFRASTRUCTURE & INTER-SERVICE PIPELINES

- [ ] Initialize Supabase PostgreSQL schema with `projects`, `tasks`, `compliance_checks`, `pipeline_progress`, `generated_ads`, and `ad_policy_rules` tables
- [ ] Configure unified environment secrets (`.env`) for Gemini, AWS S3, Supabase, Qdrant, ElevenLabs, and Zernio SDK
- [ ] Establish resilient client initialization with try/except fallback for S3, Supabase, and Qdrant connections
- [ ] Implement a local `FallbackQueue` to catch and defer failed persistence operations without halting pipeline execution
- [ ] Wire FastAPI `app.py` entry point with CORS middleware, exception handlers, and modular router registration
- [ ] Build shared S3 pre-signed URL helpers (`generate_presigned_upload_url`, `upload_file_public`, `get_public_url`) for two-phase browser-to-S3 uploads

---

### 2) MULTI-MODAL COMPLIANCE CHECK PIPELINE (LANGGRAPH)

- [ ] Define `Compliance_State` TypedDict with session, media, market, platform, ethnicity, and result fields
- [ ] Build Pydantic structured output schemas (`ComplianceAnalysisSchema`, `JudgesEvaluationSchema`, `TranscribeSchema`) for enforced Gemini JSON responses
- [ ] Implement `fetch_rules_and_personas` node — Supabase query for market/platform rules + Qdrant vector similarity for regulatory citations
- [ ] Implement `transcribe_media` node — Gemini multimodal transcription for audio/video with language detection
- [ ] Implement `main_brain_analysis` node — cross-references media content against fetched rules using role-specific prompts per media type
- [ ] Implement `judges_agent` node — secondary evaluation for bias detection, hallucination scoring, and claims grounding verification
- [ ] Write pure `route_compliance_decision` function mapping risk_level + risk_percentage → `pass` / `remediate` / `critical_regen`
- [ ] Compile LangGraph `StateGraph` with conditional edges routing audio/video through transcription, text/image direct to analysis
- [ ] Build `ProgressTracker` to record step-level status (running/completed/error) to `pipeline_progress` table for frontend polling

---

### 3) AGENTIC AD GENERATION ENGINE (LANGGRAPH FAN-OUT)

- [ ] Define `GenerationState` TypedDict with project context, detected media types, generated ads list, and pipeline state canvas
- [ ] Implement `detect_media_types` intent classifier — Gemini NLP classification with deterministic keyword fallback for robustness
- [ ] Build `platform_rules.py` — Supabase lookup for platform-specific aspect ratios, max dimensions, and duration limits
- [ ] Implement four independent media agent modules (`text_agent`, `image_agent`, `audio_agent`, `video_agent`) each with identical `generate()` contract
- [ ] Wire LangGraph fan-out topology: `load_history → resolve_platform → detect_intent → [conditional fan-out to N agents] → collect → persist → emit`
- [ ] Build `compliance_bridge.py` — automatically invokes compliance pipeline for each generated ad and maps verdict to final status
- [ ] Implement `chat_store.py` for persisting user/assistant chat turns with 10,000-character truncation and fallback queue on failure
- [ ] Construct `_build_pipeline_state` to assemble React Flow-compatible canvas nodes/edges for frontend visualization

---

### 4) AUTOMATED REMEDIATION PIPELINE (HUMAN-IN-THE-LOOP)

- [ ] Define `Remediation_State` TypedDict extending compliance result with aspect_ratio, remediation_plan, and remediated_paths
- [ ] Implement `fetch_compliance_result` node — retrieves prior check violations and constructs remediation plan
- [ ] Implement `confirm_aspect_ratio` node — uses LangGraph `interrupt()` for human-in-the-loop confirmation via WebSocket resume
- [ ] Build media-specific remediation handlers: image inpainting (Gemini Imagen), text rewrite (Gemini), audio TTS (ElevenLabs), video keyframe editing (FFmpeg)
- [ ] Implement `upload_and_finalize` node — S3 upload of remediated asset + Supabase status update
- [ ] Build image quality scoring function — blank image detection (std_dev < 5) and pixel difference comparison
- [ ] Wire `PipelineRunner` with `asyncio.Event`-based human decision handling and configurable timeout

---

### 5) PUBLISHING GATE & SOCIAL DISTRIBUTION

- [ ] Implement `publish_ad` function — idempotent publishing with compliance gate that blocks `final-non-compliant` ads
- [ ] Build `distribute_ad` function — Zernio SDK `posts.create()` with platform account resolution from environment variables
- [ ] Map platform-specific settings (TikTok privacy, Instagram format, YouTube metadata)
- [ ] Implement post-distribution metadata recording (`distributed_at`, `distribution_platform`, `distribution_post_id`) with non-fatal failure handling
- [ ] Build `get_ad_analytics` — Zernio analytics retrieval with mock fallback when API key is missing

---

### 6) FRONTEND WORKSPACE & REAL-TIME DASHBOARDS

- [ ] Scaffold React 19 + TypeScript + Vite + Tailwind CSS 4 + shadcn/ui application with `@/` path alias
- [ ] Implement AWS Cognito OAuth authentication flow with `oidc-client-ts` UserManager and session rehydration
- [ ] Build onboarding wizard — company profile form with Supabase persistence and `is_onboarded` gate
- [ ] Develop project management pages — create, list, navigate projects and tasks with CRUD operations
- [ ] Build generation chat workspace (`guidedGenerate.tsx`) — SSE stream consumption, React Flow pipeline canvas, storyboard viewer
- [ ] Build compliance dashboard (`compliance.tsx`) — SSE progress stepper, risk score visualization, violation overlay on media
- [ ] Implement two-phase S3 direct upload flow — presigned URL request → browser PUT to S3
- [ ] Build assets page — grid view of all generated media with type filtering, platform tags, and download links
- [ ] Implement statistics page (`statistics.tsx`) — Recharts integration with Zernio engagement/reach/CTR metrics
- [ ] Build trends page (`trends.tsx`) — cultural event timeline + platform trend cards with engagement sparklines

---

### 7) CAPCUT DRAFT EXPORT & VIDEO TOOLING

- [ ] Integrate `pycapcut` / `pyJianYingDraft` library for CapCut-compatible project draft generation
- [ ] Implement video + image overlay draft creation with configurable transitions (fade, dissolve)
- [ ] Build FFmpeg duration detection and keyframe extraction utilities
- [ ] Implement draft ZIP download endpoint and auto-install-to-CapCut folder detection
- [ ] Build dual-output endpoint — generates both CapCut draft and rendered MP4 simultaneously

---

### ADDITIONAL OPERATIONAL UTILITIES & QUALITY ASSURANCE

- [ ] Deploy Qdrant vector ingestion scripts for regulatory rule embeddings (JAKIM, ASA, CVM/CONAR)
- [ ] Build Apify + Gemini GoogleSearch scraper for weekly trend cache refresh
- [ ] Implement PredictHQ cultural events sync for religious/festive/national event tagging
- [ ] Configure Vitest + fast-check property-based testing for frontend UI invariants
- [ ] Configure pytest with coverage reporting for backend pipeline unit tests
- [ ] Build WebSocket `ConnectionManager` for real-time result delivery and human-in-the-loop interrupt relaying
- [ ] Implement dark/light mode theming via `next-themes` with system preference detection
- [ ] Deploy GSAP entrance animations with `useGSAP` scoped containers for dashboard polish
- [ ] Configure ElevenLabs voice cloning manager for brand-consistent audio remediation

---

## 4.6.1 Backend Orchestration: Compliance Check Pipeline
**File:** [backend/jusads_compliance/compliance_pipeline.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_compliance/compliance_pipeline.py)

### [Screenshot: Pydantic schemas and output validation setup]
**Figure 4.1:** Pydantic Schemas for Structured AI Compliance Output Validation

#### Explanation:
Before the AI can judge whether an ad is compliant, the system needs to agree on exactly what a compliance result should look like. That is the job of these Pydantic schemas — they act as a binding contract between JusAds and the Gemini model. `ComplianceAnalysisSchema` tells Gemini that every response must include a numeric risk score between 0 and 100, a severity label, a plain-English verdict, a list of specific cultural or regulatory violations with timestamps for video content, a localisation suggestion, and an overall cultural fit score for the target SEA market. By passing this schema directly into the model's configuration as a `response_schema`, the backend never has to guess whether the AI remembered to include a particular field. Any downstream pipeline node — such as the judges verification step or the decision router — can read these fields directly without defensive try/except wrappers around every key lookup, which makes the entire system more reliable and easier to maintain.

---

### [Screenshot: LangGraph workflow compilation and execution DAG]
**Figure 4.2:** LangGraph StateGraph Workflow Compilation and Node Mapping

#### Explanation:
This code is where the compliance checking pipeline is wired together into an ordered sequence of AI reasoning steps. Rather than making a single large model call and hoping for the best, JusAds breaks the analysis into five specialist stages. The first stage fetches the relevant advertising regulations and retrieves similar past enforcement cases using vector search, giving the AI proper context before it looks at the submitted content. For audio and video, a transcription stage converts spoken content into text first — images and plain text skip this via a conditional edge. The main analysis stage then cross-references the media against the fetched rules and the target audience persona. A dedicated verification stage follows, re-reading the primary result to catch hallucinations, overconfident claims, or cultural bias the first pass might have introduced. Only after all of this does the decision router apply the final verdict. Compiling and exporting the graph means any route handler can trigger this entire multi-step reasoning chain with a single `.stream()` call.

---

## 4.6.2 Backend Orchestration: Multi-Agent Ad Generation
**File:** [backend/jusads_generation/orchestrator.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_generation/orchestrator.py)

### [Screenshot: LangGraph generation state graph compile and state definition]
**Figure 4.3:** Multi-Agent Generation StateGraph Orchestration

#### Explanation:
This backend program orchestrates the creative ad generation pipeline using a multi-agent LangGraph workflow. It manages the sharing of the generation state (containing project briefings, target personas, storyboard scene specifications, and generated image URLs) between separate agent nodes. The orchestrator routes execution dynamically from intent analysis to storyboarding (Director Agent), copywriting, and image asset generation (Designer Agent), ensuring cooperative execution of specialized agents.

---

## 4.6.3 Backend Core Logic: Pure Routing Decision Engine
**File:** [backend/jusads_compliance/decision_router.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_compliance/decision_router.py)

### [Screenshot: Pure routing function execution logic]
**Figure 4.4:** Rule-Based Compliance Decision Routing Algorithm

#### Explanation:
Once the AI has scored an ad, something needs to translate that score into a clear, actionable outcome. That is the job of this small but critical function. It reads three inputs — the severity label, the numeric risk score, and any flagged high-risk indicators — and maps them to exactly one of three outcomes. A Low risk score at or below 30 means the ad passes and the user can publish. A Critical label or a score above 85 means the ad is rejected and must be fully regenerated from scratch. Everything in between triggers the targeted remediation flow, where the system attempts surgical fixes rather than starting over. The function is written intentionally with no side effects — it reads its inputs, applies the rules, and returns a result, nothing more. This makes it trivial to unit-test every possible combination of score and severity level without setting up a database connection or making any external API calls, and it ensures the compliance verdict is always predictable and fully auditable.

---

## 4.6.4 Backend API Layer: FastAPI WebSocket Streaming
**File:** [backend/routes/compliance.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/routes/compliance.py)

### [Screenshot: FastAPI WebSocket streaming router]
**Figure 4.5:** FastAPI SSE Stream Event Emitter for Compliance

#### Explanation:
This endpoint is the front door of the compliance system — the single API call that accepts an uploaded ad and sets the entire checking pipeline in motion. When a user submits a file, the handler saves it temporarily, uploads a copy to S3 so the asset is preserved regardless of what happens next, creates a task record in Supabase, and packages all the context — target market, demographic, platform — into a state dictionary. Rather than waiting for the full analysis to finish before responding, it immediately opens a live Server-Sent Events stream back to the browser. Each time a pipeline node starts or completes, a small JSON event is pushed to the client so the compliance dashboard can advance its progress stepper in real time. The final event carries the complete compliance report including risk score, violation list, and localisation suggestions. Users see the analysis progressing step by step rather than staring at a spinner waiting for everything at once.

---

## 4.6.5 Frontend User Interface: Interactive Ad Generation Studio
**File:** [frontend/src/pages/guidedGenerate.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/guidedGenerate.tsx)

### [Screenshot: React guided generation chatbot workspace and scene editor]
**Figure 4.6:** React Interactive Ad Studio Chat Workspace UI

#### Explanation:
This frontend TypeScript React page provides the user interface for the interactive ad generation workspace. It sets up a real-time conversation screen that communicates with the backend orchestrator via WebSockets. It enables the user to chat with the AI Director, dynamically render generated storyboards, edit visual briefs, view intermediate asset generations, and customize target platform parameters in real-time.

---

## 4.6.6 Frontend User Interface: Compliance Progress & Violations Page
**File:** [frontend/src/pages/compliance.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/compliance.tsx)

### [Screenshot: React compliance monitoring interface with progress bar and rule citations]
**Figure 4.7:** React Compliance Monitoring Dashboard

#### Explanation:
This is the page users see while an ad is being checked and after the result comes back. It connects to the backend event stream and listens for the sequence of progress events that the pipeline emits as each node completes. Each event advances an animated stepper indicator, so users can see which stage the analysis is at — whether it is still transcribing the audio, running the main analysis, or going through the verification pass. When the final event arrives, the page switches from progress mode to result mode: it shows the overall risk score as a colour-coded gauge, renders any flagged violations as highlighted overlays directly on top of the uploaded image or video, lists the specific regulatory rules that were breached with links to the original citations, and shows the AI's suggested fixes. If the ad needs remediation, a single button kick-starts the auto-fix pipeline without requiring the user to navigate elsewhere.

---

## 4.6.7 Frontend User Interface: Marketing Analytics & Performance Dashboard
**File:** [frontend/src/pages/statistics.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/statistics.tsx)

### [Screenshot: React marketing statistics page with chart rendering and Zernio client integrations]
**Figure 4.8:** React Social Media Post Performance Dashboard

#### Explanation:
After ads are distributed to TikTok or Instagram, this page is where users come to see how they are performing. It fetches live metrics from the `/api/statistics/posts` endpoint, which aggregates data from the Zernio distribution platform, and presents them in two sections. The first section covers JusAds-published campaigns specifically — posts that were generated and distributed through the platform — showing impressions, likes, engagement rate, and reach per post in a sortable table. The second section shows a broader account-level overview: total followers reached across all connected profiles, a bar chart comparing platform performance side by side, and a table of all organic posts on the connected accounts including ones that were not created through JusAds. This gives users a complete picture of their social presence, not just the ads they ran through the tool, making it easier to understand how JusAds-generated content compares to their regular posting activity.

---

## 4.6.8 Backend Orchestration: Automated Remediation Pipeline
**File:** [backend/jusads_compliance/remediation_pipeline.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_compliance/remediation_pipeline.py)

### [Screenshot: Remediation StateGraph — nodes, edges, and interrupt mechanism]
**Figure 4.9a:** LangGraph Remediation Pipeline with Human-in-the-Loop Interrupt

#### Explanation:
When a compliance check finds violations, this pipeline handles fixing them automatically so users do not have to edit the ad manually. The repair process runs as its own four-stage LangGraph graph, completely separate from the compliance pipeline. The first stage loads the prior check result from Supabase and uses the violation list to build a targeted fix plan — only the specific elements that were flagged get touched. The second stage pauses the pipeline using LangGraph's `interrupt()` mechanism and asks the user to confirm the output format before any media processing begins, because generating a remediated asset at the wrong aspect ratio would be wasted work. Once the user responds via WebSocket, the pipeline resumes. The third stage routes to the appropriate repair tool depending on media type. The final stage uploads the fixed asset to S3 and updates the compliance record in Supabase to reflect the new remediated status.

---

### [Screenshot: _remediate_text function — Gemini JSON rewrite prompt and response parsing]
**Figure 4.9b:** Text Remediation — Gemini-Powered Ad Copy Rewrite

#### Explanation:
When ad copy is flagged — whether for making exaggerated product claims, using language that is offensive to a particular ethnic group, or breaching platform-specific copy guidelines — this handler rewrites it without changing what the ad is actually selling. It takes the original text from the compliance result alongside the list of specific violations and the AI's own suggested correction, then asks Gemini to return a revised version as a structured JSON object containing both the rewritten text and an explicit list of every change that was made. Returning JSON rather than free text means the handler can reliably extract the corrected copy without parsing around conversational preamble. The rewritten text is saved to a temporary file and handed off to the upload node, producing a clean compliant version ready to drop back into the campaign.

---

### [Screenshot: _remediate_audio function — ElevenLabs TTS call with brand voice lookup]
**Figure 4.9c:** Audio Remediation — ElevenLabs Text-to-Speech Re-Recording

#### Explanation:
For audio ads with non-compliant spoken content, editing the waveform directly is not practical — the cleanest fix is to re-record the audio from a corrected script. This handler uses the compliance pipeline's own suggestion field as the replacement script, so the corrected content is already available without any additional AI call. It then resolves the appropriate ElevenLabs voice for the target market and demographic by querying the `brand_voices` table in Supabase, ensuring the replacement recording uses the same voice profile that was intended for the original ad. The `eleven_multilingual_v2` model handles the synthesis across Malay, Mandarin, Tamil, and English — all common in Malaysian advertising — and the output is streamed chunk-by-chunk into a `.mp3` file that the finalize node uploads to S3.

---

### [Screenshot: _remediate_image function — Imagen inpainting loop with mask fallback chain and quality gate]
**Figure 4.9d:** Image Remediation — Iterative Imagen Inpainting with Quality Gate

#### Explanation:
Fixing a non-compliant image means replacing only the specific violating region — a patch of exposed skin, a non-halal symbol, or an offensive gesture — while keeping everything else in the creative exactly as it was. This handler implements that using Gemini Imagen's inpainting API with a three-tier mask resolution strategy. If the compliance pipeline produced segmentation data and stored a mask URL, that mask is used directly. If only a segmented overlay image is available, the handler generates a binary mask by comparing it against the original using pixel-difference analysis. If neither exists, it falls back to a full-image mask so the operation can still proceed. The inpainting is then attempted up to three times: after each attempt, a quality scoring function checks whether the result is visually coherent and sufficiently different from the violation — a score below 70 out of 100 triggers a refined prompt for the next retry. This retry loop exists because inpainting results can be inconsistent, and spending two extra API calls to reach an acceptable quality threshold is better than surfacing a low-quality fix to the user.

---

### [Screenshot: _remediate_video function — FFmpeg keyframe extraction and violations_timeline handling]
**Figure 4.9e:** Video Remediation — Keyframe Extraction and I2V Segment Replacement

#### Explanation:
Video remediation is the most structurally complex of the four handlers because compliance violations in video are time-bound — the compliance pipeline does not just say what is wrong, it says exactly when it appears. This handler works from the `violations_timeline` list, which contains the start and end timestamps of every flagged segment. It downloads the source video, uses FFmpeg to extract a reference keyframe from the first violation's start timestamp, and constructs a Gemini prompt describing what compliant replacement content should look like for that segment given the video's aspect ratio and the specific violations. The strategy is recorded as `video_i2v` — image-to-video — in the output metadata, and the result is passed to the finalize node for S3 upload. The timeline-based approach means the system can target individual seconds of a thirty-second ad rather than forcing a full regeneration when only a brief segment is non-compliant.

---

## 4.6.9 Backend API Layer: Distribution and Publishing Endpoints
**File:** [backend/jusads_generation/publish.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_generation/publish.py) + [backend/jusads_generation/distribution.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_generation/distribution.py)

### [Screenshot: publish_ad compliance gate and distribute_ad Zernio SDK call]
**Figure 4.10:** Publishing Gate and Social Media Distribution via Zernio SDK

#### Explanation:
Getting an ad from the generation workspace to a live social platform is a deliberate two-step process, and both steps are protected. The publish step is where the system enforces its most important safety rule: no ad that was found non-compliant after remediation can ever be published. The `publish_ad` function checks the compliance status stored in Supabase before doing anything else, and if the status is `final-non-compliant` it raises a hard error that the API converts to a 409 response. This is not just a warning — it is a structural block that no frontend workaround can bypass. For ads that clear this check, the function sets the status to published with a UTC timestamp and handles double-submissions gracefully by returning a quiet success if the ad was already marked published.

Once published, the distribution step handles the actual delivery. The `distribute_ad` function checks that a Zernio API key is configured, resolves the correct social media account for the chosen platform from environment variables, and calls `client.posts.create()` with the ad's S3 URL, caption, and platform-specific settings. TikTok posts include privacy controls; Instagram posts use the appropriate media format. The post ID that Zernio returns is saved back into the `generated_ads` table, creating the link that the analytics dashboard uses to fetch engagement metrics for that specific post after it goes live.

---

## 4.6.10 Frontend Intelligence: Trend Analysis Dashboard
**File:** [frontend/src/pages/trends.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/trends.tsx)

### [Screenshot: Trend Intelligence Dashboard with event calendar and industry intel cards]
**Figure 4.11:** React Trend Intelligence and Cultural Event Calendar

#### Explanation:
The Trends page exists to answer a practical question that every ad team faces: what is actually resonating with audiences right now, and what cultural moments are coming up that could make a campaign land harder? The page answers both sides of that question simultaneously. On the cultural calendar side, it calls the events endpoint with the user's market and displays upcoming religious, festive, national, and sports events over the next 60 days — each card showing the event name, type, date range, and an impact score so teams can prioritise their campaign timing. The market selector lets users switch between Malaysia, Singapore, Thailand, Indonesia, Vietnam, and the Philippines without leaving the page, auto-detecting the most likely default from the user's browser timezone.

On the trend intelligence side, the page fetches high-performing content scraped weekly from TikTok, Instagram, YouTube, and Facebook Ads. Each piece of content is shown as a card with its view count, engagement velocity score, associated hashtags, and a direct link to the original post. A platform filter lets users narrow the feed to a specific channel. When the system detects that trending content overlaps with an upcoming cultural event — for example, a wave of Raya-themed content appearing close to Eid al-Fitr — it surfaces a Synergy Insight banner at the top of the page highlighting the overlap and estimating the engagement uplift, with a direct shortcut to the generation workspace to capitalise on the timing.
