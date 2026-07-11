# Chapter 4: Design and Implementation

This document contains the implementation details, including the development plan task list (Section 4.5.1) and critical code sections with explanations (Section 4.6), structured for copy-pasting directly into your FYP report.

---

## 4.5.1 Development Plan

To ensure software reliability and smooth debugging, the system architecture was systematically broken down into distinct functional modules. This allowed the developer to decouple complex computational intelligence tasks from standard frontend document manipulation and user experience rendering. Managing the implementation through targeted feature checklist clusters proved to be highly effective for the development process. 

Below is the structured step-by-step development plan and task list designed to guide the replication or rebuilding of a similar AI-driven ad generation and compliance checking platform.

### Phase 1: Environment Setup & Foundation
- [ ] **Database Initialization:** Setup a relational database schema (e.g., PostgreSQL via Supabase) containing tables for `projects`, `tasks`, `compliance_checks`, `pipeline_progress`, and `ad_policy_rules`.
- [ ] **Infrastructure & Clients Configuration:** Setup environment configurations (`.env`) and initialize unified clients for cloud storage (AWS S3), vector databases (Qdrant), and LLM frameworks (Google Vertex AI / Gemini SDK).
- [ ] **Asynchronous Error Resiliency:** Implement a local fallback retry queue (`fallback_queue.py`) to catch failed database writes/updates and queue them for deferred retries without halting core execution threads.

### Phase 2: Backend Orchestration – Multi-Agent Generation Engine
- [ ] **Graph State & Typed Schema:** Define the multi-agent shared state representation using Python `TypedDict` (`state.py`) to store creative parameters, scripts, scene briefs, and media metadata.
- [ ] **Task Intent Detection:** Develop a natural language processing node (`intent.py`) to analyze incoming user briefs and classify the target media type (text, image, audio, or video).
- [ ] **Creative Agent Nodes:** Implement specialized agent modules (Director, Copywriter, Designer, Audio Composer) using Vertex AI models, wrapping scriptwriting, visual brief generation, and asset descriptions.
- [ ] **LangGraph Orchestration:** Construct the state machine graph (`orchestrator.py`) linking agent nodes together to automate the ad storyboard generation workflow.

### Phase 3: Backend Orchestration – Compliance Check Pipeline
- [ ] **Structured Validation Schemas:** Define strict Pydantic model response templates (`ComplianceAnalysisSchema` and `JudgesEvaluationSchema`) to enforce structured JSON outputs from Vertex AI.
- [ ] **Rule Retrieval Engine:** Write a database lookup helper (`rules_client.py`) to query regional and platform-specific advertising rules (e.g., JAKIM Halal rules for Malaysia, CVM/CONAR rules for Brazil).
- [ ] **Transcription & OCR Pre-processing:** Implement nodes to extract text components (e.g., ElevenLabs audio transcription, video frame scanning via Gemini).
- [ ] **Multi-Agent Evaluation & Quality Check:** Configure a compliance audit node (Main Brain) followed by a secondary verification node (Judges Agent) to evaluate bias and score claims grounding (hallucination checks).
- [ ] **Decision Routing:** Write a pure routing node (`decision_router.py`) to map compliance metrics (risk percentages and level classifications) to outcomes (`pass`, `remediate`, or `critical_regen`).

### Phase 4: Frontend Development – User Workspace & Dashboards
- [ ] **Vite React Boilerplate:** Scaffold the React 19 application with TypeScript, Tailwind CSS, and shadcn/ui components.
- [ ] **Interactive Generation Chat Workspace:** Develop the chat workspace (`guidedGenerate.tsx`) to allow users to interact with the AI Director, view storyboards, and edit visual asset details.
- [ ] **Real-time Pipeline Tracker:** Build the compliance dashboard (`compliance.tsx`) that listens to backend WebSocket event feeds, rendering pipeline steppers, risk percentages, and overlaying violations onto media assets.
- [ ] **Zernio Client Analytics Integration:** Build the statistics page (`statistics.tsx`) using rendering libraries (Recharts) to chart clicks, reach, and engagement pulled from Zernio social publishing endpoints.

### Phase 5: Automated Remediation & Media Processing
- [ ] **FFmpeg Subtitle & Audio Mixing:** Setup local command-line scripts (`remediation_executor.py`) to run FFmpeg commands to burn subtitles onto video clips, mix audio tracks, and adjust clip speeds.
- [ ] **Remix Action Router:** Develop a heuristic and AI-driven router to identify appropriate remediation tools based on the flagged compliance violations.

---

## 4.6.1 Backend Orchestration: Compliance Check Pipeline
**File:** [backend/jusads_compliance/compliance_pipeline.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/jusads_compliance/compliance_pipeline.py)

### [Screenshot: Pydantic schemas and output validation setup]
**Figure 4.1:** Pydantic Schemas for Structured Vertex AI Output Validation

#### Explanation:
This backend code block defines the structured data models using Pydantic (`BaseModel`) to enforce strict type-safety and schemas for all responses returned from Google Vertex AI (Gemini 3.5 Flash). By passing schemas like `ComplianceAnalysisSchema` and `JudgesEvaluationSchema` directly to the model configuration, the orchestrator guarantees that unstructured textual outputs are validated, parsed, and converted to structured objects. This ensures that downstream nodes in the LangGraph workflow can reliably read values such as risk percentage, explanation, and high-risk indicators without encountering JSON parsing or schema mismatch errors.

---

### [Screenshot: LangGraph workflow compilation and execution DAG]
**Figure 4.2:** LangGraph StateGraph Workflow compilation and node mapping

#### Explanation:
This code block constructs and compiles the state graph (`StateGraph`) that orchestrates the execution of the compliance checking nodes. Using nodes (`fetch_rules_and_personas`, `transcribe_media`, `main_brain_analysis`, `judges_agent`, `decision_router`) and conditional edges, the compliance pipeline runs the appropriate transcription checks for audio/video media and switches to direct text/image checks, preserving shared pipeline state (`Compliance_State`) before terminating at the END node.

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
This pure routing function maps the compliance audit results to one of three standardized outcomes: `pass`, `critical_regen`, or `remediate`. It is written as a side-effect-free function to enable testability. It evaluates the quantitative risk percentage alongside the qualitative risk classification and high-risk indicators to determine whether the advertisement requires direct rejection or simple automated remediation.

---

## 4.6.4 Backend API Layer: FastAPI WebSocket Streaming
**File:** [backend/routes/compliance.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/routes/compliance.py)

### [Screenshot: FastAPI WebSocket streaming router]
**Figure 4.5:** FastAPI WebSocket Stream Event Emitter

#### Explanation:
This endpoint is the FastAPI handler that streams live execution events from the compiled LangGraph pipeline directly to the client's dashboard. It loops over the asynchronous generator of the pipeline runner, serializing and pushing live progress updates (e.g., transcription started, analysis completed) via the active WebSocket channel to display immediate feedback on the user interface.

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
This frontend React page renders the real-time compliance checking dashboard. It connects to the backend WebSocket stream, parsing progress updates to render styled stepper indicators for each node in the LangGraph checking pipeline. It displays the final compliance verdict, overlays visual violations onto images/videos, lists high-risk indicators, and provides links to verified regulatory citations and enforcement cases.

---

## 4.6.7 Frontend User Interface: Marketing Analytics & Performance Dashboard
**File:** [frontend/src/pages/statistics.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/statistics.tsx)

### [Screenshot: React marketing statistics page with chart rendering and Zernio client integrations]
**Figure 4.8:** React Marketing Analytics and Post Performance Chart

#### Explanation:
This frontend React component renders the post-distribution marketing statistics dashboard. It integrates with the Zernio distribution client APIs, retrieving analytics for published ads (reach, engagement rate, click-through-rate, and conversions). It parses the raw stats dataset, mapping it onto responsive charts to give users a clear, statistical understanding of how their ad copy is performing across platforms.
