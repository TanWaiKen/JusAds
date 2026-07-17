# Chapter 4.6 — Implementation Code (Use Case Mapping)

This document maps each Use Case from `diagram/jusads_usecase.drawio` to the four implementation layers: Backend Logic, FastAPI Gateway Router, Endpoint, and Frontend Request. Each layer includes a figure caption with the exact file and line range to screenshot, followed by an explanation.

---

## UC-01: Login

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/profile.py` | — |
| FastAPI Gateway | `backend/routes/profile.py` | `GET /api/user/{email}` |
| Frontend | `frontend/src/lib/authProvider.tsx` + `frontend/src/hooks/useAuth.ts` | — |

### 1) Code in Backend

**File:** `backend/routes/profile.py`, lines 35–55

### [Screenshot: get_or_create_user function]
**Figure 4.6.1a:** User Session Retrieval and Auto-Registration Endpoint

#### Explanation:
This backend function implements the Login use case's server-side persistence. When a user authenticates via AWS Cognito OAuth, the frontend calls this endpoint with the user's email. The function queries the Supabase `users` table — if the record exists, it returns it immediately; if not, it inserts a new row with `is_onboarded: False`. This "get-or-create" pattern ensures that every authenticated Cognito user automatically gets a backend record on first login without requiring a separate registration step. The function is wrapped in try/except for resilient degradation if Supabase is temporarily unreachable.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/profile.py`, lines 20–22 (router declaration) + lines 35–39 (endpoint decorator and signature)

### [Screenshot: APIRouter declaration and @router.get("/user/{email}") decorator]
**Figure 4.6.1b:** FastAPI Profile Router Registration

#### Explanation:
The `APIRouter(prefix="/api", tags=["profile"])` declaration establishes the `/api` URL namespace for all profile-related endpoints. The `@router.get("/user/{email}")` decorator maps HTTP GET requests to the `get_or_create_user` async function, with FastAPI automatically extracting the `email` path parameter and validating it as a string. The router is registered in `app.py` via `app.include_router(profile_router)`.

---

### 3) Endpoint

**Endpoint:** `GET /api/user/{email}`

| Method | URL | Auth Required | Response |
|--------|-----|---------------|----------|
| GET | `/api/user/{email}` | No (post-Cognito callback) | `{ email, is_onboarded, created_at }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/lib/authProvider.tsx`, lines 41–86

### [Screenshot: AuthProvider useEffect with session rehydration and userManager.getUser()]
**Figure 4.6.1c:** React Auth Session Rehydration via oidc-client-ts

#### Explanation:
The frontend `AuthProvider` component uses `oidc-client-ts` UserManager to interface with AWS Cognito. On mount, it attempts to rehydrate the session by calling `userManager.getUser()`. Upon successful authentication (or silent token renewal), the user's email is extracted from the JWT `profile` claims. The frontend then calls `GET /api/user/{email}` to sync the backend state, determining whether to show the onboarding wizard or redirect to the dashboard. The `useAuth()` hook (`frontend/src/hooks/useAuth.ts`, lines 1–20) exposes the authenticated user context to all child components.


---

## UC-02: User Onboarding

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/profile.py` | — |
| FastAPI Gateway | `backend/routes/profile.py` | `POST /api/profile` |
| Frontend | `frontend/src/pages/onboarding.tsx` | — |

### 1) Code in Backend

**File:** `backend/routes/profile.py`, lines 77–111

### [Screenshot: create_or_update_profile function with Supabase upsert]
**Figure 4.6.2a:** Business Profile Upsert and Onboarding Completion Logic

#### Explanation:
This function handles the onboarding flow's data persistence. It receives a `BusinessProfileRequest` Pydantic model containing `owner_email`, `company_name`, `product_category`, `product_description`, `target_platforms`, and `target_markets`. It upserts the row into the `business_profiles` table using the `on_conflict="owner_email"` strategy, then sets `is_onboarded = True` on the `users` table. This two-table atomic update ensures that the system correctly tracks onboarding completion and can gate access to the dashboard accordingly.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/profile.py`, lines 76–79 (decorator + signature)

### [Screenshot: @router.post("/profile") decorator and BusinessProfileRequest body]
**Figure 4.6.2b:** FastAPI Onboarding Endpoint with Pydantic Request Validation

#### Explanation:
The `@router.post("/profile")` decorator maps the POST method to the `create_or_update_profile` handler. FastAPI automatically deserializes the JSON request body into the `BusinessProfileRequest` Pydantic model (lines 24–30), which enforces type validation on all fields — including the list types for `target_platforms` and `target_markets`. If the body fails validation, FastAPI returns a 422 response before the handler is invoked.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/profile` | `{ owner_email, company_name, product_category, product_description, target_platforms[], target_markets[] }` | `{ success: true, profile: {...} }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/pages/onboarding.tsx`, lines 86–108

### [Screenshot: handleSubmit function with fetch POST to /api/profile]
**Figure 4.6.2c:** React Onboarding Form Submission with JSON Payload

#### Explanation:
The `handleSubmit` function validates that all required fields (company name, product category, platforms, markets) are filled before firing a `fetch` POST to `${API_BASE}/api/profile`. The JSON body maps directly to the backend `BusinessProfileRequest` schema. On success (HTTP 200), the component navigates to the dashboard. On failure, it displays a toast error notification. The `useAuth()` hook provides the current user's email for the `owner_email` field.


---

## UC-04: Create Project

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/projects.py` | — |
| FastAPI Gateway | `backend/routes/projects.py` | `POST /api/projects` |
| Frontend | `frontend/src/services/taskApi.ts` | — |

### 1) Code in Backend

**File:** `backend/routes/projects.py`, lines 55–67

### [Screenshot: create_project function with SupabaseComplianceStore.create_project call]
**Figure 4.6.3a:** Project Creation with Supabase Persistence Store

#### Explanation:
The `create_project` handler validates that the Supabase store is available (returning 503 if not), then delegates to `store.create_project(user_id, name)`. The store inserts a new row into the `projects` table with the owner's email, project name, and auto-generated timestamps. The function returns HTTP 201 with the created project object (including the server-generated UUID). Error handling wraps the database call — any exception yields a 500 response without exposing internal details.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/projects.py`, lines 17–18 (router declaration) + lines 55–57 (endpoint decorator)

### [Screenshot: APIRouter(prefix="/api") and @router.post("/projects") decorator]
**Figure 4.6.3b:** FastAPI Projects Router with Pydantic CreateProjectRequest Validation

#### Explanation:
The Projects router uses `APIRouter(prefix="/api", tags=["projects"])`. The `CreateProjectRequest` Pydantic model (lines 40–52) validates the input body, enforcing that `name` is a non-empty stripped string via a custom `@field_validator`. This ensures no blank project names reach the database. The router is wired into the app via `init_store(supabase_store)` at startup, which injects the shared persistence client.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/projects` | `{ name: string, username: string }` | `201 { id, name, owner_email, created_at, updated_at }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/taskApi.ts`, lines 90–100

### [Screenshot: createGenerationTask function with fetch POST]
**Figure 4.6.3c:** Frontend Project and Task Creation via TaskApi Service

#### Explanation:
The frontend service layer abstracts all project/task API calls. `createGenerationTask` sends a `POST` to `/api/projects/{projectId}/tasks` with the task type. For project creation itself, the `newProject.tsx` page calls the equivalent function with `{ name, username }` body. The service uses the `API_BASE` environment variable (defaulting to `http://localhost:8000`) and propagates HTTP errors as thrown exceptions for the UI to handle with toast notifications.


---

## UC-05: Generate Ad Creative (text/image/audio/video)

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/jusads_generation/orchestrator.py`, `agents/text_agent.py`, `agents/image_agent.py`, `agents/audio_agent.py`, `agents/video_agent.py` | — |
| FastAPI Gateway | `backend/routes/generation.py` | `POST /api/projects/{pid}/tasks/{tid}/chat` |
| Frontend | `frontend/src/services/generationApi.ts` | — |

### 1) Code in Backend

**File:** `backend/jusads_generation/orchestrator.py`, lines 545–594

### [Screenshot: build_graph() function — StateGraph node registration, conditional fan-out edges, and compilation]
**Figure 4.6.4a:** Multi-Agent LangGraph StateGraph Orchestration for Ad Generation

#### Explanation:
This function builds and compiles the ad generation state graph using the LangGraph framework. The graph registers eleven nodes in total — seven core orchestration nodes and four media-specific agent nodes. The core nodes handle preparatory tasks such as retrieving prior chat context, normalising the target platform's sizing rules, and classifying the user's intent into one or more media types. Upon classification, a conditional edge fans execution out exclusively to the agents that the user actually requested. For instance, if a user only asks for a poster, only the image agent receives work while text, audio, and video agents remain idle. After all activated agents complete, a join node merges their outputs before the final nodes persist the assistant's response and assemble a React Flow-compatible canvas that the frontend renders as an interactive pipeline diagram. The compiled graph is cached at module level to avoid recompilation overhead on every request.

---

**File:** `backend/jusads_generation/agents/text_agent.py`, lines 140–200

### [Screenshot: text_agent generate() function with Gemini caption generation and S3 upload]
**Figure 4.6.4b:** Text Copy Agent — Gemini-Powered Caption Generation with GoogleSearch Context

#### Explanation:
The text agent implements the standardised media agent contract. When invoked, it first queries Gemini's GoogleSearch grounding tool to gather trending creative context from the Malaysian advertising market. This external knowledge enriches the generation prompt beyond the user's brief alone. The agent then calls Gemini to produce a culturally localised ad caption, writes the result to a temporary file, uploads it to AWS S3 under a project-scoped key, and records a row in the generated_ads Supabase table. If any step fails, the agent records a failure status without disrupting sibling agents — maintaining the fan-out isolation guarantee.

---

**File:** `backend/jusads_generation/agents/image_agent.py`, lines 262–330

### [Screenshot: image_agent generate() function with Imagen generation, reference parts handling, and fallback]
**Figure 4.6.4c:** Image Creator Agent — Native Imagen Generation with Platform-Aware Sizing

#### Explanation:
The image agent generates visual ad creatives at the exact aspect ratio and maximum dimension specified by the target platform's rules. It enriches the user's brief with trending visual market context from GoogleSearch, then refines the prompt using a platform-specific style guide loaded from a local JSON configuration. The primary generation path uses Google's native Imagen model via the Gemini SDK. If reference images were uploaded by the user, these are passed as multimodal context to influence the style and composition. Should the native generation fail, a fallback mechanism creates a placeholder graphic to ensure the pipeline never halts entirely. The final image is uploaded to S3 and persisted as a completed asset record.

---

**File:** `backend/jusads_generation/agents/audio_agent.py`, lines 260–320

### [Screenshot: audio_agent generate() function with ElevenLabs TTS and Gemini script writing]
**Figure 4.6.4d:** Audio Composer Agent — Gemini Scriptwriting with ElevenLabs Text-to-Speech

#### Explanation:
The audio agent first invokes Gemini to compose a voiceover script suited to the target platform and audience demographic. The script is then synthesised into an MP3 file using the ElevenLabs text-to-speech API with a preconfigured brand voice. The resulting audio file is uploaded to S3 and the asset metadata is persisted to Supabase. Platform-aware duration limits are enforced to ensure the generated voiceover does not exceed maximum ad length constraints for the target social media platform.

---

**File:** `backend/jusads_generation/agents/video_agent.py`, lines 250–320

### [Screenshot: video_agent generate() function with Gemini Omni video generation and S3 upload]
**Figure 4.6.4e:** Video Generator Agent — Google Gemini Omni AI Video Creation

#### Explanation:
The video agent is the most computationally intensive of the four media agents. It constructs a video generation prompt from the user's brief and passes it to Google's Gemini Omni model (gemini-omni-flash-preview) via the Gemini SDK, requesting VIDEO and AUDIO response modalities. The model generates the entire video clip in a single call — no clip-by-clip stitching or frame interpolation required. Gemini Omni natively produces both video and background audio. When the ad requires human narration, a separate ElevenLabs voiceover is generated and merged on top via ffmpeg. Like all agents, it operates in complete isolation from its siblings and records its own success or failure independently.

---

**File:** `backend/jusads_generation/intent.py`, lines 72–110

### [Screenshot: detect_media_types function with Gemini classification and keyword fallback]
**Figure 4.6.4f:** Intent Detection — NLP Media Type Classification with Gemini and Keyword Fallback

#### Explanation:
The intent detection function serves as the routing gate that determines which media agents will be activated for a given user message. It sends the natural language brief to Gemini with a classification prompt designed to extract the desired output formats. Gemini returns a JSON array containing any combination of text, image, audio, and video identifiers. If the Gemini API is unavailable or returns an unusable response, the system falls back to a deterministic keyword-based classifier that scans for action verbs paired with media-related nouns. An empty result from both classifiers triggers the clarification flow, prompting the user to explicitly state what type of creative they need.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/generation.py`, lines 100–172

### [Screenshot: chat_with_generation_agent SSE endpoint with ChatRequest model and background task setup]
**Figure 4.6.4g:** FastAPI Generation Chat Endpoint with Background SSE Streaming

#### Explanation:
This endpoint serves as the HTTP bridge between the frontend chat interface and the backend generation orchestrator. It accepts a comprehensive request model containing the user's message alongside optional configuration for guided mode, reference image URLs, target platform, demographic targeting, and cultural localisation parameters. The handler validates the task's existence, persists the user's chat turn to Supabase for history retrieval, then launches the generation pipeline as an independent background task. Server-Sent Events are pushed through an asynchronous queue and streamed to the client in real time. Critically, the background task continues executing even if the client disconnects mid-stream, ensuring that generated ads are always persisted to the database regardless of network interruptions.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/projects/{project_id}/tasks/{task_id}/chat` | `{ message, target_platform, reference_urls[], skip_compliance, video_v3, target_ethnicity, age_group, market, language, product_name, product_category, gender }` | SSE stream with events: text chunks, node status updates, pipeline state canvas, error notifications |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/generationApi.ts`, lines 127–163

### [Screenshot: sendChat function with fetch POST and JSON.stringify body]
**Figure 4.6.4h:** Frontend SSE Chat Request to Generation Agent

#### Explanation:
The frontend service function serialises the generation request as a JSON POST and returns the raw Response object to the calling page component. The caller then consumes the response body as a readable stream, parsing each Server-Sent Events line into typed event objects. Text chunks are rendered progressively in the chat interface, node status events update the pipeline canvas visualisation to show which agent is currently active, and the final pipeline state event triggers a full canvas re-render with the generated ads populated in the output gallery. The default platform is applied automatically when the user has not explicitly selected one, ensuring the backend always receives a valid platform identifier.


---

## UC-06: Ad Compliance and Localization Check

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/jusads_compliance/compliance_pipeline.py` + `backend/jusads_compliance/decision_router.py` | — |
| FastAPI Gateway | `backend/routes/compliance.py` | `POST /api/compliance/check` |
| Frontend | `frontend/src/services/complianceApi.ts` | — |

### 1) Code in Backend

**File:** `backend/jusads_compliance/compliance_pipeline.py`, lines 40–84

### [Screenshot: Pydantic schemas — ComplianceAnalysisSchema, TranscribeSchema, ViolationTimelineItem]
**Figure 4.6.5a:** Pydantic Schemas for Structured Vertex AI Compliance Output Validation

#### Explanation:
Before the AI can judge whether an ad is compliant or not, the system needs to agree on exactly what "a compliance result" looks like. That is what these Pydantic schemas do — they act like a contract between JusAds and the Gemini model. `ComplianceAnalysisSchema` tells Gemini to always return a risk score between 0 and 100, a severity label (Low / Moderate / High / Critical), a plain-English verdict, a list of specific cultural or regulatory violations, timestamped violation markers for video content, a localisation suggestion, and an overall cultural fit score for the target SEA market. By handing this schema directly to Gemini as a `response_schema`, the backend never has to guess whether the AI remembered to include a field — it is enforced at the model level. Any downstream pipeline node, like the judges verification step or the decision router, can safely read these fields straight away without fragile string parsing or defensive try/except wrappers around every key lookup.

---

**File:** `backend/jusads_compliance/compliance_pipeline.py`, lines 868–896

### [Screenshot: StateGraph compilation — nodes, conditional edges, and compliance_pipeline export]
**Figure 4.6.5b:** LangGraph Compliance StateGraph Compilation and Node Wiring

#### Explanation:
This is the part of the code that decides the order in which the AI "thinks" about an ad. The compliance check is not a single model call — it is a five-step pipeline stitched together with LangGraph. The first node fetches the relevant advertising rules from the database and retrieves the most similar past regulatory cases using vector search, so the AI has proper context before it looks at anything. For audio and video uploads, a transcription node runs next to convert spoken content into text the language model can reason about — images and plain text skip this step via a conditional edge. The main analysis node then cross-references everything: the media content, the fetched rules, and the audience persona. After the primary analysis, a second AI node called `judges_agent` re-reads the result specifically looking for hallucinations, overconfident claims, or cultural bias. Only then does the decision router apply the final pass/remediate/reject verdict. Exporting the compiled graph as `compliance_pipeline` means any route handler can invoke this entire multi-step process with a single `.stream()` call.

---

**File:** `backend/jusads_compliance/decision_router.py`, lines 17–60

### [Screenshot: route_compliance_decision pure function with pass/critical_regen/remediate logic]
**Figure 4.6.5c:** Pure Compliance Decision Routing Algorithm

#### Explanation:
Once the AI has scored an ad, something needs to translate that score into a clear action. That is the job of this small but important function. It takes three things — the severity label, the numeric risk percentage, and any flagged high-risk indicators — and maps them to one of three outcomes. If the risk is Low and the score is 30 or below, the ad passes and the user can publish. If the risk is Critical or the score is above 85, the ad is rejected outright and must be fully regenerated. Everything in between triggers the remediation flow, where the AI attempts targeted fixes rather than starting over. The function is intentionally written with no side effects — it reads its inputs and returns an outcome, nothing more. This makes it straightforward to unit-test every possible score combination without setting up a database or making API calls, and it ensures the compliance verdict is always predictable and auditable.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/compliance.py`, lines 119–200

### [Screenshot: POST /api/compliance/check endpoint with FormData handling, S3 upload, and state construction]
**Figure 4.6.5d:** FastAPI Compliance Check SSE Endpoint with Media Upload and Pipeline Invocation

#### Explanation:
This is the front door of the compliance system — the single endpoint that accepts an ad from the browser and sets the entire checking pipeline in motion. When a user uploads a file, the endpoint saves it temporarily, uploads a copy to S3 so the asset is preserved regardless of what happens next, and creates a task record in Supabase so the check can be retrieved later. It then packages all the context — who is checking, which market and demographic the ad targets, which platform it is for — into a single state dictionary and hands it to the LangGraph pipeline. Rather than waiting for the full analysis to finish before responding, the endpoint streams live progress back to the browser using Server-Sent Events. Each time a pipeline node starts or finishes, the browser receives a small JSON event that the compliance dashboard uses to light up the progress stepper in real time. The completed result, including risk score, violations, and suggestions, is saved to the `compliance_checks` table and emitted as the final stream event so the frontend can render the full report.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/compliance/check` | `FormData { file?, text?, market, ethnicity, age_group, platform, username, project_id }` | SSE stream: `{type:"initiated"}`, `{type:"node_status"}`, `{type:"result", data:{...}}` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/complianceApi.ts`, lines 204–256

### [Screenshot: checkComplianceStream function with FormData construction and SSE ReadableStream parsing]
**Figure 4.6.5e:** Frontend Compliance Check SSE Consumer with Line-by-Line Event Parsing

#### Explanation:
On the browser side, submitting an ad for compliance checking is handled by this service function. It packages the uploaded file — or raw text — together with the market, demographic, age group, and platform settings into a `FormData` object, then sends it to the backend as a streaming HTTP request. Instead of waiting for a single JSON response, the function reads the reply as a continuous byte stream, splitting each `data:` line into individual events and passing them one by one to an `onEvent` callback. The compliance dashboard listens for these events in order: the first event confirms the check has started, subsequent events advance the step indicators as each pipeline node completes, and the final event carries the full compliance report including the risk score, violation list, and localisation suggestions. This streaming approach means users see the analysis progressing in real time rather than staring at a spinner waiting for everything to finish at once.


---

## UC-07: Ad Remediation (auto-fix violations)

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/jusads_compliance/remediation_pipeline.py` | — |
| FastAPI Gateway | `backend/routes/compliance.py` | `POST /api/compliance/{task_id}/remediate` |
| Frontend | `frontend/src/services/complianceApi.ts` | — |

### 1) Code in Backend

**File:** `backend/jusads_compliance/remediation_pipeline.py`, lines 419–435

### [Screenshot: Remediation StateGraph compilation — nodes and edges]
**Figure 4.6.6a:** LangGraph Remediation Pipeline StateGraph Compilation

#### Explanation:
When a compliance check finds violations, the user does not have to manually fix the ad themselves — JusAds can attempt to repair it automatically. This code sets up the four-step repair pipeline. The first node loads the prior check result and uses the violations list to build a targeted fix plan, so the remediation is surgical rather than starting from scratch. The second node does something unusual: it pauses the pipeline entirely and asks the user a question. Using LangGraph's `interrupt()` mechanism, it emits a message to the frontend asking the user to confirm the output aspect ratio before any media is processed, because reformatting an image or video to the wrong dimensions would waste time and compute. Once the user responds through the WebSocket, the pipeline resumes. The third node then branches based on media type to one of the four specialist handlers below. The final node uploads the fixed asset to S3 and updates the compliance record in Supabase to reflect the remediated status.

---

**File:** `backend/jusads_compliance/remediation_pipeline.py`, lines 417–463

### [Screenshot: _remediate_text function — Gemini JSON rewrite with violations list and suggestion]
**Figure 4.6.6b:** Text Remediation — Gemini-Powered Ad Copy Rewrite

#### Explanation:
When the compliance check flags an ad's written copy — for example a claim that is too aggressive for Malaysian advertising standards, or language that is culturally insensitive to a target ethnicity — this handler rewrites it automatically. It retrieves the original text from the compliance result, assembles a structured prompt that lists the specific violations and the AI's own suggested fix, then asks Gemini to return a corrected version as a JSON object containing the rewritten text and a list of the changes made. Using `response_mime_type="application/json"` prevents Gemini from adding conversational filler around the answer. The corrected copy is saved to a temporary `.txt` file which the `upload_and_finalize` node then pushes to S3, producing a ready-to-use compliant version of the text ad. The original language and brand voice are preserved — only the non-compliant elements are changed.

---

**File:** `backend/jusads_compliance/remediation_pipeline.py`, lines 465–505

### [Screenshot: _remediate_audio function — ElevenLabs TTS with voice lookup]
**Figure 4.6.6c:** Audio Remediation — ElevenLabs Text-to-Speech Re-Recording

#### Explanation:
For audio ads that contain non-compliant spoken content — such as prohibited financial claims, misleading health statements, or culturally inappropriate phrasing — this handler regenerates the audio from scratch rather than attempting to edit the waveform. It takes the AI's remediation suggestion as the replacement script (the compliance pipeline already produces a corrected version of what should have been said), looks up the appropriate brand voice for the target market and demographic from the Supabase `brand_voices` table via `get_voice()`, then calls the ElevenLabs `text_to_speech.convert()` API with the `eleven_multilingual_v2` model. The audio stream is written chunk-by-chunk to a temporary `.mp3` file. This approach guarantees that the replacement audio uses the same culturally matched voice profile as the original intended broadcast, ensuring brand consistency in the remediated output.

---

**File:** `backend/jusads_compliance/remediation_pipeline.py`, lines 237–360

### [Screenshot: _remediate_image function — Imagen inpainting loop with mask generation and quality scoring]
**Figure 4.6.6d:** Image Remediation — Iterative Imagen Inpainting with Quality Gate

#### Explanation:
Fixing a non-compliant image — such as one showing exposed skin that violates Malaysian modesty standards, or a logo that infringes brand guidelines — requires surgically replacing only the violating region while leaving the rest of the creative intact. This handler implements that as a retry loop with a quality gate. It starts by downloading the original image and resolving a pixel-level mask that marks which area needs to be replaced: if the compliance pipeline ran segmentation and stored a mask URL, that mask is downloaded and used directly; if not, the handler generates a binary mask by comparing the original image against any segmentation overlay; and as a last resort it creates a full-image mask so the operation can still proceed. It then builds an inpainting prompt from the specific violation labels and the AI's localisation suggestion, and calls Gemini Imagen's `edit_image()` API with `EDIT_MODE_INPAINT_INSERTION`. After each attempt, a quality scoring function compares the inpainted result against the original using pixel-difference analysis — if the score is below 70 out of 100, the prompt is refined and the call retried up to three times. Only when quality is sufficient, or the retry budget is exhausted, does the handler pass the output path to the finalize node for S3 upload.

---

**File:** `backend/jusads_compliance/remediation_pipeline.py`, lines 361–415

### [Screenshot: _remediate_video function — FFmpeg keyframe extraction and I2V segment replacement]
**Figure 4.6.6e:** Video Remediation — Keyframe Extraction and I2V Segment Replacement

#### Explanation:
Video remediation is the most structurally complex of the four handlers because violations are time-bound — the compliance pipeline identifies not just what is wrong but at which exact timestamps the problem occurs. This handler works from the `violations_timeline` list, which contains start and end timestamps for each flagged segment. It downloads the source video, then uses FFmpeg to extract a reference keyframe from the first violation's start timestamp — this keyframe serves as the visual anchor for the replacement generation. A Gemini prompt is built describing what compliant content should look like given the video's aspect ratio and the specific violations listed. The strategy is recorded as `video_i2v` and the output path is passed to the `upload_and_finalize` node, which stores the result and updates the compliance record so users can see the remediated version alongside the original in their assets gallery.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/compliance.py`, lines 268–323

### [Screenshot: POST /api/compliance/{task_id}/remediate endpoint with Remediation_State construction]
**Figure 4.6.6f:** FastAPI Remediation Endpoint with Human-in-the-Loop Interrupt Handling

#### Explanation:
This endpoint bridges the compliance result stored in the database with the live remediation pipeline. It looks up the prior check using the `task_id`, reconstructs all the violation context, and feeds everything into the remediation runner as a streaming SSE response. What makes this endpoint interesting is how it handles the mid-pipeline pause. When the pipeline reaches the aspect ratio confirmation node, it stops and emits a `human_review` event back to the browser. The frontend shows a selection modal to the user. When the user picks an option, the browser sends a WebSocket message containing their decision, which triggers an `asyncio.Event` on the server side. This unblocks the pipeline runner, which then continues from exactly where it paused and proceeds with the remediation using the user's chosen dimensions. The entire pause-resume cycle happens transparently within a single streaming HTTP response, keeping the connection alive the whole time.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/compliance/{task_id}/remediate` | None (uses task_id to fetch prior result) | SSE stream: `{type:"node_status"}`, `{type:"human_review"}`, `{type:"result"}` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/complianceApi.ts`, lines 260–290 (approx.)

### [Screenshot: startRemediation function or equivalent fetch call to /remediate]
**Figure 4.6.6g:** Frontend Remediation Trigger and WebSocket Human Decision Relay

#### Explanation:
From the user's perspective, clicking "Auto-Fix" on a non-compliant ad fires this service function. It sends a single `POST` request to the remediation endpoint and immediately begins reading the response as an event stream. Most events are straightforward progress updates — "fetching violations", "rewriting text", "uploading result" — and the dashboard renders these as animated step completions. The interesting moment is when a `human_review` event arrives: the UI pauses the progress display and renders a modal asking the user to pick the output format. Once the user selects an option, the WebSocket sends the decision to the server and the dashboard resumes showing progress until the final remediated asset URL arrives. The user ends up with a ready-to-use fixed version of their ad without ever having to touch the underlying media manually.


---

## UC-11: Distribute Assets to Social Media

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/jusads_generation/distribution.py` + `backend/jusads_generation/publish.py` | — |
| FastAPI Gateway | `backend/routes/generation.py` | `POST .../ads/{ad_id}/publish` + `POST .../ads/{ad_id}/distribute` |
| Frontend | `frontend/src/services/generationApi.ts` | — |

### 1) Code in Backend

**File:** `backend/jusads_generation/publish.py`, lines 67–113

### [Screenshot: publish_ad function with compliance gate and idempotent publishing]
**Figure 4.6.7a:** Human-in-the-Loop Publishing Gate with Compliance Block

#### Explanation:
This function acts as the last safety checkpoint before any JusAds-generated ad reaches a live social platform. Before marking an ad as published, it checks the ad's compliance status stored in Supabase. If the ad was flagged as `final-non-compliant` — meaning it went through remediation and still did not meet the required standards — the function raises a `CompliancePublishBlockedError` and the request is rejected with a 409 response. This hard block means no amount of manual retries from the frontend can bypass a flagged ad. For ads that are compliant or still pending a final compliance verdict, the function sets the status to "published" with an ISO UTC timestamp. It also checks whether the ad has already been published and returns a quiet success in that case, making the operation safe to call more than once without creating duplicate records.

---

**File:** `backend/jusads_generation/distribution.py`, lines 78–151

### [Screenshot: distribute_ad function with Zernio SDK client.posts.create call]
**Figure 4.6.7b:** Zernio SDK Social Media Distribution with Platform Account Resolution

#### Explanation:
Once an ad is marked as published, this function handles the actual delivery to TikTok or Instagram. The first thing it does is confirm that a Zernio API key exists in the environment — if it does not, the distribution is rejected immediately rather than silently failing later. It then resolves which social account to post to by reading platform-specific account IDs from environment variables, so the same codebase can serve multiple brand accounts without any code changes. The ad's S3 URL, caption, and media type are then packaged into a `client.posts.create()` call. TikTok posts include privacy settings to control who can view them, while Instagram posts use the appropriate media format. When the post goes live, Zernio returns a post ID which is stored back in the `generated_ads` table alongside a timestamp and the platform name, giving the analytics layer something concrete to query against later.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/generation.py`, lines 364–384 (publish) + lines 393–442 (distribute)

### [Screenshot: publish_generated_ad and distribute_generated_ad route handlers]
**Figure 4.6.7c:** FastAPI Publish and Distribute Endpoints with Error Mapping

#### Explanation:
These two route handlers are the HTTP layer that the frontend calls when a user clicks "Publish" or "Distribute" on an ad card. The publish handler tries to mark the ad as ready for distribution and maps each possible failure to a meaningful HTTP status: a 404 if the ad cannot be found, a 409 if the compliance gate is blocking it, and a 500 for unexpected errors. The distribute handler works the same way — a 409 if the social account credentials are not configured, and a 500 for SDK-level failures. Mapping domain-specific exceptions to standard HTTP codes keeps the frontend code simple: it just checks the status code and picks the right toast message without needing to inspect error payloads. Both responses include enough detail for the UI to update the ad card's status badge in place without requiring a full page reload.

---

### 3) Endpoints

| Method | URL | Response |
|--------|-----|----------|
| POST | `/api/projects/{pid}/tasks/{tid}/ads/{ad_id}/publish` | `{ ad_id, status:"published", already_published: bool }` |
| POST | `/api/projects/{pid}/tasks/{tid}/ads/{ad_id}/distribute` | `{ post_id, status:"distributed", platform }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/generationApi.ts`, lines 165–195 (approx.)

### [Screenshot: publishAd and distributeAd fetch POST calls]
**Figure 4.6.7d:** Frontend Publish and Distribute API Integration

#### Explanation:
From the user's side, publishing and distributing an ad are two separate button presses, and these service functions handle each one. `publishAd` sends a `POST` to the publish endpoint and, on success, the ad card's status badge flips from "completed" to "published" with a green indicator — a small but important visual cue that the ad is ready to go out. `distributeAd` takes a platform argument so the user can choose TikTok or Instagram independently, sending that choice in the request body. Both functions throw on any non-2xx response, which the workspace page catches and surfaces as a toast notification explaining what went wrong — whether the ad was blocked for compliance, the account is not connected, or something unexpected happened on the server. This two-step publish-then-distribute flow gives the user one last chance to review before the ad actually reaches a live audience.


---

## UC-12: Social Media Post Live Analysis

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/statistics.py` + `backend/shared/zernio_client.py` | — |
| FastAPI Gateway | `backend/routes/statistics.py` | `GET /api/statistics` |
| Frontend | `frontend/src/services/statisticsApi.ts` | — |

### 1) Code in Backend

**File:** `backend/routes/statistics.py`, lines 33–43

### [Screenshot: get_statistics_overview function with get_overall_analytics() call]
**Figure 4.6.8a:** Zernio Live Analytics API Bridge

#### Explanation:
The statistics endpoint directly calls the Zernio production API (no caching) via the `get_overall_analytics()` wrapper. This function aggregates impressions, clicks, engagement rate, reach, conversions, likes, comments, and shares across all distributed posts on all connected platforms. It returns the raw Zernio response — real-time metrics that the frontend renders into Recharts visualizations. Error handling wraps the external call with a 500 response on failure.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/statistics.py`, lines 28–32 (router + decorator)

### [Screenshot: APIRouter(prefix="/api/statistics") and @router.get("") decorator]
**Figure 4.6.8b:** FastAPI Statistics Router with Multiple Metric Endpoints

#### Explanation:
The statistics router exposes five endpoints under `/api/statistics`: root (overall), `/daily` (daily aggregates), `/best-times` (optimal posting times), `/accounts` (connected accounts), and `/posts` (per-post breakdown). Each endpoint delegates to a specific Zernio client wrapper, maintaining separation between the API transport layer and the external SDK integration.

---

### 3) Endpoints

| Method | URL | Response |
|--------|-----|----------|
| GET | `/api/statistics` | `{ overview, per_post[], platform_breakdown }` |
| GET | `/api/statistics/daily` | `{ daily_metrics[] }` |
| GET | `/api/statistics/posts` | `{ jusads_posts[], jusads_totals, jusads_count }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/statisticsApi.ts`, lines 79–96

### [Screenshot: fetchPostStatistics function with fetch to /api/statistics/posts]
**Figure 4.6.8c:** Frontend Statistics API Fetch with Platform Filtering

#### Explanation:
The `fetchPostStatistics` function calls `/api/statistics/posts` with an optional platform query parameter. The returned data is mapped into the `StatsResponse` interface containing `jusads_posts` (individual post metrics), `jusads_totals` (aggregated KPIs), and `jusads_count`. The `statistics.tsx` page renders this data using Recharts line/bar charts showing engagement over time, reach trends, and platform-level performance comparisons.


---

## UC-14: Trending Analysis based on Company Context

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/trends.py` | — |
| FastAPI Gateway | `backend/routes/trends.py` | `GET /api/trends` |
| Frontend | `frontend/src/services/trendsApi.ts` | — |

### 1) Code in Backend

**File:** `backend/routes/trends.py`, lines 26–81

### [Screenshot: get_trends function with Supabase query, platform grouping, and last_refresh mapping]
**Figure 4.6.9a:** Trend Intelligence Data Retrieval and Platform Grouping

#### Explanation:
The trends system is built around a weekly scraping job that pulls high-performing content from TikTok, Instagram, YouTube, and Facebook Ads, storing everything in a `trends_cache` table in Supabase. This endpoint is what the frontend calls to read that cache. It applies optional filters for platform and market so a Malaysian food brand sees different trending content than a Singapore fashion label. Results are sorted by recency and grouped by platform, making it straightforward for the frontend to render separate sections per channel. Each trend item carries the engagement numbers — views, likes, shares, comments — alongside hashtags, content categories, and a cultural event tag if the content was associated with a festive or religious occasion. The `last_refresh` timestamps are included in the response so the frontend can show users how fresh the data is, and if the cache is empty a friendly message explains that the scraper runs on a weekly schedule rather than showing a confusing blank page.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/trends.py`, lines 17–25 (router declaration + endpoint decorator)

### [Screenshot: APIRouter(prefix="/api/trends") and @router.get("") with query parameters]
**Figure 4.6.9b:** FastAPI Trends Router with Optional Platform and Market Filters

#### Explanation:
The trends router exposes four endpoints under a single `/api/trends` prefix, each serving a distinct purpose. The root listing returns scraped social content filtered by platform and market. The events endpoint returns upcoming cultural and religious occasions for a given country within a configurable day window — useful for timing campaigns around Hari Raya, Chinese New Year, or national holidays. A sync endpoint lets admins trigger a fresh pull from PredictHQ on demand, and a refresh endpoint initiates a new scraping cycle. FastAPI's `Optional[str]` query parameters handle all the filtering with sensible defaults, meaning the frontend can call these endpoints with no parameters at all and still get meaningful results for the default market.

---

### 3) Endpoint

| Method | URL | Params | Response |
|--------|-----|--------|----------|
| GET | `/api/trends` | `?platform=tiktok&market=malaysia&limit=50` | `{ trends: {platform: items[]}, last_refresh: {platform: timestamp}, total_items }` |
| GET | `/api/trends/events` | `?market=malaysia&window_days=60` | `{ events[], global_events[], national_events[], market, count }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/trendsApi.ts`, lines 62–73

### [Screenshot: fetchTrends function with URLSearchParams and fetch to /api/trends]
**Figure 4.6.9c:** Frontend Trends API Fetch with Dynamic Query Parameters

#### Explanation:
This service function is what the Trends page calls whenever the user changes the platform filter or switches the market dropdown. It builds a clean query string from whichever combination of platform, market, and limit the user has chosen, then fetches the matching trend data. The response is typed as `TrendsResponse`, which the page uses to populate the industry intel card grid — each card showing a piece of high-performing content with its view count, engagement velocity, associated hashtags, and a direct link to the original post. If the user's business profile already has a target market set, the page passes that market by default so the trends they see on first load are relevant to their actual advertising context rather than a generic global feed. The cultural events endpoint is called in parallel using the same market value, which is why the event calendar and the trend cards update together whenever the country filter changes.


---

## UC-10: Manage Assets (S3 Direct Upload)

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/files.py` | — |
| FastAPI Gateway | `backend/routes/files.py` | `POST /api/files/upload-url` |
| Frontend | `frontend/src/services/fileService.ts` | — |

### 1) Code in Backend

**File:** `backend/routes/files.py`, lines 56–100

### [Screenshot: get_upload_url function with quota check, size validation, S3 key building, and presigned URL generation]
**Figure 4.6.10a:** Pre-signed S3 Upload URL Generation with Quota and Size Enforcement

#### Explanation:
This endpoint implements the two-phase upload pattern: the frontend requests a signed PUT URL, then uploads directly to S3 without routing the file through the API server. The function first validates the 5 GB user quota via `check_quota(username, file_size)`, then enforces the 100 MB per-file limit. It builds a unique S3 key using the pattern `{prefix}/{username}/{project_id}/{uuid}_{filename}` and generates a presigned URL with `generate_presigned_upload_url()`. The response includes the `upload_url`, `s3_key`, and `public_url` — the frontend uses these for the direct S3 PUT and subsequent metadata references.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/files.py`, lines 31–35 (router) + lines 51–55 (endpoint decorator with UploadUrlRequest model)

### [Screenshot: APIRouter(prefix="/api/files") and @router.post("/upload-url") with UploadUrlRequest body]
**Figure 4.6.10b:** FastAPI Files Router with Pydantic Upload Request Validation

#### Explanation:
The `UploadUrlRequest` Pydantic model (lines 32–38) validates `filename`, `content_type`, `file_size`, `username`, `project_id`, and `asset_type`. The router serves two endpoints: `POST /upload-url` (generates upload URL) and `POST /download-url` (generates download URL). This architecture keeps large binary files off the API server, reducing memory pressure and enabling direct S3 transfers up to 100 MB.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/files/upload-url` | `{ filename, content_type, file_size, username, project_id, asset_type }` | `{ upload_url, s3_key, public_url, filename }` |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/services/fileService.ts`, lines 40–72

### [Screenshot: uploadFileToS3 function — Step 1: POST for URL, Step 2: PUT to S3]
**Figure 4.6.10c:** Frontend Two-Phase S3 Direct Upload Implementation

#### Explanation:
The `uploadFileToS3` function executes a two-step flow: (1) `POST /api/files/upload-url` to obtain the signed URL and S3 key, then (2) `fetch(upload_url, { method: "PUT", body: file })` to upload the raw binary directly to AWS S3. This avoids the 100 MB file traversing the backend server entirely. The function returns the `s3_key` and `public_url` which the compliance check and generation flows use to reference the uploaded media.


---

## Supplementary: CapCut Draft Export

| Layer | File | Endpoint |
|-------|------|----------|
| Backend Logic | `backend/routes/capcut_draft.py` | — |
| FastAPI Gateway | `backend/routes/capcut_draft.py` | `POST /api/capcut/generate-draft` |
| Frontend | `frontend/src/pages/capcut-draft.tsx` | — |

### 1) Code in Backend

**File:** `backend/routes/capcut_draft.py`, lines 79–136

### [Screenshot: generate_draft function with pycapcut image overlay draft creation]
**Figure 4.6.11a:** CapCut Draft Generation with Video + Image Overlay via pycapcut

#### Explanation:
The `generate_draft` endpoint accepts video and image `UploadFile` objects alongside configuration parameters (draft_name, transition_type, image_duration, canvas dimensions, FPS). It saves both files to a temp directory, then calls `_create_image_overlay_draft()` which uses the `pycapcut` library to construct a CapCut/JianYing-compatible project draft. The draft includes the video as the base track, the image as an overlay layer, and a configurable transition (fade/dissolve) between segments. The generated draft is saved as a ZIP that the user can download and import into CapCut desktop.

---

### 2) Code in FastAPI Gateway Router

**File:** `backend/routes/capcut_draft.py`, lines 25–27 (router) + lines 79–92 (endpoint decorator with Form parameters)

### [Screenshot: APIRouter(prefix="/api/capcut") and @router.post("/generate-draft") with File + Form params]
**Figure 4.6.11b:** FastAPI CapCut Router with Multipart File + Form Parameter Binding

#### Explanation:
The router uses FastAPI's `File(...)` for binary uploads and `Form(default=...)` for named parameters. This allows a single multipart request to carry both the video/image files and the configuration options (transition type, dimensions, FPS) without requiring a separate JSON body. The CAPCUT_AVAILABLE flag gates the endpoint — returning 503 if neither `pycapcut` nor `pyJianYingDraft` are installed.

---

### 3) Endpoint

| Method | URL | Body | Response |
|--------|-----|------|----------|
| POST | `/api/capcut/generate-draft` | `FormData { video: File, image: File, draft_name, transition_type, image_duration_sec, width, height, fps }` | `{ success, download_url, draft_name, video_duration_sec, canvas }` |
| GET | `/api/capcut/download/{draft_name}` | — | ZIP FileResponse |

---

### 4) Frontend Endpoint Request

**File:** `frontend/src/pages/capcut-draft.tsx` (approx. lines 80–110)

### [Screenshot: FormData construction with video + image files and fetch POST to /api/capcut/generate-draft]
**Figure 4.6.11c:** Frontend CapCut Draft Generation Form Submission

#### Explanation:
The CapCut draft page provides file input fields for video and image, plus dropdowns for transition type and canvas dimensions. On submit, it constructs a `FormData` with both files and all form parameters, then fires a `POST` to `/api/capcut/generate-draft`. On success, it displays the download link which triggers a browser download of the ZIP draft file via `/api/capcut/download/{draft_name}`.

---

## Figure Reference Summary

| Figure | File | Lines | Caption |
|--------|------|-------|---------|
| 4.6.1a | `backend/routes/profile.py` | 35–55 | User Session Retrieval and Auto-Registration |
| 4.6.1b | `backend/routes/profile.py` | 20–22, 35–39 | FastAPI Profile Router Registration |
| 4.6.1c | `frontend/src/lib/authProvider.tsx` | 41–86 | React Auth Session Rehydration |
| 4.6.2a | `backend/routes/profile.py` | 77–111 | Business Profile Upsert and Onboarding |
| 4.6.2b | `backend/routes/profile.py` | 76–79 | FastAPI Onboarding Endpoint |
| 4.6.2c | `frontend/src/pages/onboarding.tsx` | 86–108 | React Onboarding Form Submission |
| 4.6.3a | `backend/routes/projects.py` | 55–67 | Project Creation with Supabase |
| 4.6.3b | `backend/routes/projects.py` | 17–18, 55–57 | FastAPI Projects Router |
| 4.6.3c | `frontend/src/services/taskApi.ts` | 90–100 | Frontend Task Creation |
| 4.6.4a | `backend/jusads_generation/orchestrator.py` | 545–594 | Multi-Agent LangGraph StateGraph |
| 4.6.4b | `backend/jusads_generation/agents/text_agent.py` | 140–200 | Text Copy Agent — Gemini Caption Generation |
| 4.6.4c | `backend/jusads_generation/agents/image_agent.py` | 262–330 | Image Creator Agent — Imagen with Platform Sizing |
| 4.6.4d | `backend/jusads_generation/agents/audio_agent.py` | 260–320 | Audio Composer Agent — ElevenLabs TTS |
| 4.6.4e | `backend/jusads_generation/agents/video_agent.py` | 250–320 | Video Generator Agent — Gemini Omni |
| 4.6.4f | `backend/jusads_generation/intent.py` | 72–110 | Intent Detection NLP Classification |
| 4.6.4g | `backend/routes/generation.py` | 100–172 | FastAPI Generation Chat SSE Endpoint |
| 4.6.4h | `frontend/src/services/generationApi.ts` | 127–163 | Frontend SSE Chat Request |
| 4.6.5a | `backend/jusads_compliance/compliance_pipeline.py` | 40–84 | Pydantic Compliance Schemas |
| 4.6.5b | `backend/jusads_compliance/compliance_pipeline.py` | 868–896 | LangGraph Compliance StateGraph |
| 4.6.5c | `backend/jusads_compliance/decision_router.py` | 17–60 | Pure Decision Routing Algorithm |
| 4.6.5d | `backend/routes/compliance.py` | 119–200 | FastAPI Compliance Check SSE Endpoint |
| 4.6.5e | `frontend/src/services/complianceApi.ts` | 204–256 | Frontend Compliance SSE Consumer |
| 4.6.6a | `backend/jusads_compliance/remediation_pipeline.py` | 419–435 | LangGraph Remediation Pipeline |
| 4.6.6b | `backend/jusads_compliance/remediation_pipeline.py` | 417–463 | Text Remediation — Gemini Rewrite |
| 4.6.6c | `backend/jusads_compliance/remediation_pipeline.py` | 465–505 | Audio Remediation — ElevenLabs TTS |
| 4.6.6d | `backend/jusads_compliance/remediation_pipeline.py` | 237–360 | Image Remediation — Imagen Inpainting |
| 4.6.6e | `backend/jusads_compliance/remediation_pipeline.py` | 361–415 | Video Remediation — Keyframe + I2V |
| 4.6.6f | `backend/routes/compliance.py` | 268–323 | FastAPI Remediation Endpoint |
| 4.6.6g | `frontend/src/services/complianceApi.ts` | 260–290 | Frontend Remediation Trigger |
| 4.6.7a | `backend/jusads_generation/publish.py` | 67–113 | Publishing Gate with Compliance Block |
| 4.6.7b | `backend/jusads_generation/distribution.py` | 78–151 | Zernio SDK Social Distribution |
| 4.6.7c | `backend/routes/generation.py` | 364–442 | FastAPI Publish and Distribute Endpoints |
| 4.6.7d | `frontend/src/services/generationApi.ts` | 165–195 | Frontend Publish/Distribute API |
| 4.6.8a | `backend/routes/statistics.py` | 33–43 | Zernio Live Analytics Bridge |
| 4.6.8b | `backend/routes/statistics.py` | 28–32 | FastAPI Statistics Router |
| 4.6.8c | `frontend/src/services/statisticsApi.ts` | 79–96 | Frontend Statistics Fetch |
| 4.6.9a | `backend/routes/trends.py` | 26–81 | Trend Intelligence Data Retrieval |
| 4.6.9b | `backend/routes/trends.py` | 17–25 | FastAPI Trends Router |
| 4.6.9c | `frontend/src/services/trendsApi.ts` | 62–73 | Frontend Trends Fetch |
| 4.6.10a | `backend/routes/files.py` | 56–100 | Pre-signed S3 Upload URL Generation |
| 4.6.10b | `backend/routes/files.py` | 31–55 | FastAPI Files Router |
| 4.6.10c | `frontend/src/services/fileService.ts` | 40–72 | Frontend Two-Phase S3 Upload |
| 4.6.11a | `backend/routes/capcut_draft.py` | 79–136 | CapCut Draft Generation |
| 4.6.11b | `backend/routes/capcut_draft.py` | 25–27, 79–92 | FastAPI CapCut Router |
| 4.6.11c | `frontend/src/pages/capcut-draft.tsx` | 80–110 | Frontend CapCut Form Submission |
