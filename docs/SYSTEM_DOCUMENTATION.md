# JusAds — System Documentation

**Version:** 2.0  
**Date:** July 3, 2026  
**Authors:** Development Team  

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Module Structure](#4-module-structure)
5. [Key Libraries & Dependencies](#5-key-libraries--dependencies)
6. [Use Case Diagram](#6-use-case-diagram)
7. [Class Diagram](#7-class-diagram)
8. [Activity Diagrams](#8-activity-diagrams)
9. [Sequence Diagrams](#9-sequence-diagrams)
10. [Test Cases](#10-test-cases)
11. [Before vs After Comparison](#11-before-vs-after-comparison)
12. [Future Plan](#12-future-plan)

---

## 1. System Overview

JusAds is an AI-powered advertising compliance and generation platform for Southeast Asian markets (primarily Malaysia). It provides:

- **Multi-modal ad generation** — Text, image, audio, and video ad creation via AI agents
- **Cultural compliance checking** — Automated regulatory and cultural sensitivity analysis
- **Multi-scene video production** — Storyboard planning with Veo 3 dynamic video synthesis
- **Social distribution** — Direct publishing to TikTok/Instagram via Zernio API
- **Prompt library** — 14,642 searchable prompt templates via vector similarity (Qdrant)
- **Conditional localization** — Ethnicity-aware cultural rules (Malay/Chinese/Indian)

### Core Workflow
```
User Brief → AI Generation → Compliance Check → Human Approval → Social Distribution
```

---

## 2. Technology Stack

### Backend (Python 3.12 / FastAPI)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | FastAPI + uvicorn (async ASGI) | REST API + SSE streaming |
| AI/LLM | Google Gemini 2.5 Flash (Vertex AI) | Text generation, compliance analysis, prompt refinement |
| Image Gen | Imagen 4.0 (primary), Gemini Flash Lite (fallback) | Keyframe and ad image generation |
| Video Gen | Google Veo 3.0 / 3.1 Lite | Dynamic video clip synthesis (image-to-video) |
| Voice/Audio | ElevenLabs Multilingual v3 | TTS voiceover + sound effects |
| Orchestration | LangGraph (StateGraph) | Pipeline orchestration with typed state |
| Vector DB | Qdrant Cloud | Prompt template similarity search (768-dim, cosine) |
| Embeddings | Gemini text-embedding-004 | 768-dimensional text embeddings |
| Cloud Storage | AWS S3 | Media file storage (generated ads, references) |
| Database | Supabase (PostgreSQL) | Projects, tasks, generated_ads, compliance_checks |
| Distribution | Zernio API | Social media publishing (TikTok, Instagram) |
| Media Processing | FFmpeg | Video transitions, subtitle burn, audio mixing |

### Frontend (TypeScript / React 19)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | React 19 + TypeScript | SPA with type safety |
| Build | Vite 8 | Fast dev/build tooling |
| Styling | Tailwind CSS 4 | Utility-first CSS |
| UI Components | shadcn/ui (Radix) | Accessible component primitives |
| Animation | GSAP 3.15 + @gsap/react | Smooth entrance/interaction animations |
| Routing | react-router v7 | Client-side routing |
| Auth | oidc-client-ts (Cognito) | OAuth authentication |
| Charts | Recharts | Analytics visualization |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React SPA)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Dashboard │  │  Canvas  │  │  Assets  │  │ Compliance Page   │  │
│  │   Pages   │  │(Generate)│  │  Library │  │ (Check + Remix)   │  │
│  └─────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│        │              │              │                  │             │
│        └──────────────┴──────────────┴──────────────────┘             │
│                              │ HTTP/SSE                               │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────────┐
│                      BACKEND (FastAPI)                                │
│                              │                                        │
│  ┌───────────────────────────┴────────────────────────────────────┐  │
│  │                     routes/ (API Layer)                         │  │
│  │  generation.py │ compliance.py │ projects.py │ remix.py │ ...  │  │
│  └───────────┬────────────┬───────────────┬───────────────────────┘  │
│              │            │               │                           │
│  ┌───────────▼──┐  ┌─────▼────────────┐  ┌──────────────────────┐  │
│  │jusads_       │  │jusads_           │  │     shared/           │  │
│  │generation/   │  │compliance/       │  │  clients.py           │  │
│  │              │  │                  │  │  s3_client.py         │  │
│  │ orchestrator │  │ compliance_      │  │  supabase_client.py   │  │
│  │ agents/      │  │ pipeline         │  │  elevenlabs_utils.py  │  │
│  │ prompt_      │  │ remediation      │  │  models.py            │  │
│  │ search/      │  │ remix_tools      │  │  config.py            │  │
│  │ distribution │  │ decision_router  │  │  fallback_queue.py    │  │
│  └──────────────┘  └──────────────────┘  └──────────────────────┘  │
│              │            │               │                           │
└──────────────┼────────────┼───────────────┼───────────────────────────┘
               │            │               │
┌──────────────▼────────────▼───────────────▼───────────────────────────┐
│                     EXTERNAL SERVICES                                   │
│  ┌─────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │
│  │ Gemini  │ │ Veo 3  │ │Eleven   │ │  S3    │ │Supabase│ │Qdrant │ │
│  │(Vertex) │ │(Vertex)│ │Labs     │ │ (AWS)  │ │(Postgres)│ │(Cloud)│ │
│  └─────────┘ └────────┘ └─────────┘ └────────┘ └────────┘ └───────┘ │
│  ┌─────────┐ ┌────────┐                                              │
│  │ Zernio  │ │ FFmpeg │                                              │
│  │(Distrib)│ │(Local) │                                              │
│  └─────────┘ └────────┘                                              │
└───────────────────────────────────────────────────────────────────────┘
```


---

## 4. Module Structure

```
backend/
├── app.py                      # FastAPI application entry point
├── config.py                   # Re-exports from shared/config.py
├── shared/                     # SHARED utilities (cross-module)
│   ├── config.py               # Environment variables, secrets, voice config
│   ├── clients.py              # Gemini, S3, Supabase, ElevenLabs instances
│   ├── s3_client.py            # S3 operations (upload, delete, presigned)
│   ├── supabase_client.py      # Supabase CRUD (projects, tasks, checks)
│   ├── elevenlabs_utils.py     # TTS + SFX generation
│   ├── models.py               # Pydantic models (CheckRecord, etc.)
│   └── fallback_queue.py       # Deferred retry queue
├── jusads_compliance/          # COMPLIANCE pipeline
│   ├── compliance_pipeline.py  # LangGraph compliance analysis pipeline
│   ├── compliance_tools.py     # Gemini-based content analysis tools
│   ├── decision_router.py      # Pass/remediate/reject routing logic
│   ├── remediation_pipeline.py # Auto-remediation (image/audio/text)
│   ├── remix_tools.py          # Text rewrite, audio remix, image edit
│   ├── prompts.py              # All compliance prompt templates
│   ├── pipeline_runner.py      # Runs pipeline + emits WebSocket events
│   ├── progress_tracker.py     # Step-by-step progress tracking
│   ├── rules_client.py         # Qdrant regulatory rules retrieval
│   ├── triage.py               # Violation triage + severity routing
│   └── ai_designer.py          # AI-guided image edit planning
├── jusads_generation/          # GENERATION pipeline
│   ├── orchestrator.py         # LangGraph StateGraph + SSE streaming
│   ├── state.py                # TypedDict state schema
│   ├── intent.py               # Media type detection from user message
│   ├── platform_rules.py       # Platform sizing (TikTok/IG/YouTube/Shopee)
│   ├── chat_store.py           # Chat message persistence
│   ├── compliance_bridge.py    # Bridges generated ads to compliance check
│   ├── distribution.py         # Zernio social distribution
│   ├── publish.py              # Human-in-the-loop publish gate
│   ├── agents/                 # Independent media agents
│   │   ├── base.py             # Shared AgentResult contract
│   │   ├── text_agent.py       # Gemini copy generation
│   │   ├── image_agent.py      # Imagen 4 / Gemini image generation
│   │   ├── audio_agent.py      # ElevenLabs VO + SFX + mix
│   │   ├── video_agent.py      # Veo 3.0 single-clip (V1)
│   │   └── video_v2.py         # Multi-scene storyboard (V2)
│   └── prompt_search/          # Vector prompt search
│       ├── embeddings.py       # Gemini text-embedding-004
│       ├── qdrant_store.py     # Qdrant ingest + search
│       └── ingest.py           # CSV ingestion script
├── routes/                     # FastAPI route handlers
│   ├── generation.py           # Chat, publish, distribute, search
│   ├── compliance.py           # Compliance check + WebSocket
│   ├── projects.py             # Project/task CRUD
│   ├── remix.py                # Remediation endpoints
│   ├── files.py                # S3 presigned URLs
│   ├── profile.py              # User profile/onboarding
│   ├── progress.py             # Pipeline progress polling
│   └── health.py               # Health check
├── data/                       # Reference data (CSV, prompt packs)
├── tests/                      # Test scripts
├── migrations/                 # SQL schemas
└── archived/                   # Deprecated code
```


---

## 5. Key Libraries & Dependencies

### Backend (Python)

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115+ | Async web framework |
| uvicorn | 0.30+ | ASGI server |
| google-genai | latest | Gemini + Imagen + Veo via Vertex AI |
| langgraph | 0.2+ | StateGraph pipeline orchestration |
| qdrant-client | 1.9+ | Vector similarity search |
| boto3 | 1.34+ | AWS S3 + Bedrock |
| supabase | 2.0+ | PostgreSQL client |
| elevenlabs | 1.0+ | Text-to-speech + sound effects |
| pydantic | 2.0+ | Data validation + serialization |
| Pillow | 10.0+ | Image fallback generation |
| requests | 2.31+ | HTTP client (Zernio) |
| python-dotenv | 1.0+ | Environment variable loading |

### Frontend (TypeScript)

| Library | Version | Purpose |
|---------|---------|---------|
| react | 19.x | UI framework |
| typescript | 6.x | Type safety |
| vite | 8.x | Build tool |
| tailwindcss | 4.x | Styling |
| gsap | 3.15 | Animation |
| @gsap/react | 2.x | React GSAP hook |
| react-router | 7.x | Routing |
| lucide-react | latest | Icons |
| sonner | latest | Toast notifications |
| recharts | 2.x | Charts |
| oidc-client-ts | latest | OAuth (Cognito) |

---

## 6. Use Case Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              JusAds Platform                  │
                    │                                              │
   ┌────────┐      │  ┌─────────────────────────────────────┐   │
   │        │      │  │  UC1: Generate Ad Creative           │   │
   │        │──────│──│  (text/image/audio/video)            │   │
   │        │      │  └─────────────────────────────────────┘   │
   │        │      │                                              │
   │        │      │  ┌─────────────────────────────────────┐   │
   │  Ad    │──────│──│  UC2: Check Compliance               │   │
   │Manager │      │  │  (cultural + regulatory)             │   │
   │        │      │  └─────────────────────────────────────┘   │
   │        │      │                                              │
   │        │      │  ┌─────────────────────────────────────┐   │
   │        │──────│──│  UC3: Review & Publish               │   │
   │        │      │  │  (human-in-the-loop gate)            │   │
   │        │      │  └─────────────────────────────────────┘   │
   │        │      │                                              │
   │        │      │  ┌─────────────────────────────────────┐   │
   │        │──────│──│  UC4: Distribute to Social           │   │
   │        │      │  │  (TikTok / Instagram via Zernio)     │   │
   │        │      │  └─────────────────────────────────────┘   │
   │        │      │                                              │
   │        │      │  ┌─────────────────────────────────────┐   │
   │        │──────│──│  UC5: Browse Prompt Library           │   │
   │        │      │  │  (vector search + recommendations)   │   │
   │        │      │  └─────────────────────────────────────┘   │
   │        │      │                                              │
   │        │      │  ┌─────────────────────────────────────┐   │
   │        │──────│──│  UC6: Manage Projects & Assets       │   │
   │        │      │  │  (CRUD, delete with S3 cleanup)      │   │
   └────────┘      │  └─────────────────────────────────────┘   │
                    │                                              │
                    └─────────────────────────────────────────────┘
```

### Use Case Details

| UC | Actor | Precondition | Flow | Postcondition |
|----|-------|-------------|------|---------------|
| UC1 | Ad Manager | Authenticated, project exists | Configure settings → type brief → AI generates → outputs shown | Ad stored in S3 + DB |
| UC2 | Ad Manager | Ad generated | Toggle compliance ON → system auto-checks → verdict shown | Compliance result recorded |
| UC3 | Ad Manager | Ad is compliant | Click Publish → status flipped | Ad marked "published" |
| UC4 | Ad Manager | Ad is published | Click Distribute → Zernio pushes | Post live on platform |
| UC5 | Ad Manager | Qdrant ingested | Search or browse → select template → use in chat | Prompt fills chat input |
| UC6 | Ad Manager | Authenticated | Create/delete projects/tasks → S3 media cleaned up | Data removed from DB + S3 |


---

## 7. Class Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                        shared/                                      │
├────────────────────────────────────────────────────────────────────┤
│ clients.py                                                         │
│   gemini: genai.Client          (Vertex AI)                        │
│   s3: boto3.client              (AWS S3)                           │
│   supabase: Client              (Supabase)                         │
│   elevenlabs: ElevenLabs        (TTS)                              │
├────────────────────────────────────────────────────────────────────┤
│ models.py                                                          │
│   CheckRecord(BaseModel)        check_id, user_email, media_type...│
│   ComplianceOutput(BaseModel)   risk_percentage, violations...     │
│   Compliance_State(TypedDict)   session_id, media_type, result...  │
│   HistoryResponse(BaseModel)    items, total, page...              │
├────────────────────────────────────────────────────────────────────┤
│ supabase_client.py                                                 │
│   SupabaseComplianceStore       (legacy class wrapper)             │
│   create_project(user_id, name) → dict                             │
│   delete_project(project_id) → bool  [+ S3 cleanup]               │
│   delete_task(project_id, task_id) → bool  [+ S3 cleanup]         │
├────────────────────────────────────────────────────────────────────┤
│ s3_client.py                                                       │
│   upload_file_public(path, key) → url                              │
│   delete_prefix(prefix) → count                                    │
│   delete_project_media(project_id, owner) → count                  │
│   generate_presigned_url(key) → url                                │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                   jusads_generation/                                │
├────────────────────────────────────────────────────────────────────┤
│ state.py                                                           │
│   GeneratedAdRef(TypedDict)     ad_id, media_type, compliance...   │
│   GenerationState(TypedDict)    project_id, task_id, user_message..│
├────────────────────────────────────────────────────────────────────┤
│ orchestrator.py                                                    │
│   run_generation(...)           → AsyncGenerator[SSE]              │
│   run_video_plan_execution(...) → AsyncGenerator[SSE]              │
│   _enrich_brief(msg, context)   → enriched string                  │
│   _build_pipeline_state(...)    → canvas pipeline dict             │
├────────────────────────────────────────────────────────────────────┤
│ agents/base.py                                                     │
│   AgentResult(TypedDict)        ad_id, status, public_url...       │
│   generate(brief, ...) → AgentResult  [contract]                   │
├────────────────────────────────────────────────────────────────────┤
│ agents/video_v2.py                                                 │
│   Scene(TypedDict)              description, shot_type, script...  │
│   plan_video(...) → plan dict   [Phase 1: keyframes only]          │
│   execute_video_plan(plan) → AgentResult  [Phase 2: Veo render]   │
│   generate(...) → AgentResult   [one-shot full pipeline]           │
├────────────────────────────────────────────────────────────────────┤
│ distribution.py                                                    │
│   distribute_ad(ad_id, platform, url, ...) → {post_id, status}    │
│   DistributionError / AccountNotConfiguredError                    │
├────────────────────────────────────────────────────────────────────┤
│ prompt_search/qdrant_store.py                                      │
│   ingest_prompts_csv(path) → count                                 │
│   search_prompts(query, top_k) → [{title, content, score}]        │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                   jusads_compliance/                                │
├────────────────────────────────────────────────────────────────────┤
│ compliance_pipeline.py                                             │
│   compliance_pipeline (StateGraph)                                  │
│   Nodes: fetch_rules → transcribe → main_brain → judges → decide  │
├────────────────────────────────────────────────────────────────────┤
│ decision_router.py                                                 │
│   route_compliance_decision(risk, indicators) → pass/remediate/regen│
├────────────────────────────────────────────────────────────────────┤
│ remediation_pipeline.py                                            │
│   remediate_text / remediate_image / remediate_audio               │
└────────────────────────────────────────────────────────────────────┘
```


---

## 8. Activity Diagrams

### 8.1 Ad Generation Flow (Primary Service)

```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌─────────────────┐
│ User types brief│
│ in chat + sets  │
│ target settings │
└────────┬────────┘
     │
     ▼
┌─────────────────┐     ┌──────────────────┐
│ Detect Intent   │────→│ No media type?   │──→ Request clarification
│ (media types)   │     │ detected         │
└────────┬────────┘     └──────────────────┘
     │ (text/image/audio/video detected)
     ▼
┌─────────────────┐
│ Resolve Platform│
│ Rules (sizing)  │
└────────┬────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  FAN-OUT: Parallel Media Agent Dispatch  │
│                                          │
│  ┌──────┐ ┌───────┐ ┌──────┐ ┌───────┐ │
│  │ Text │ │ Image │ │Audio │ │ Video │ │
│  │Agent │ │ Agent │ │Agent │ │ Agent │ │
│  └──┬───┘ └───┬───┘ └──┬───┘ └───┬───┘ │
│     │         │         │         │      │
└─────┼─────────┼─────────┼─────────┼──────┘
      │         │         │         │
      ▼         ▼         ▼         ▼
┌─────────────────────────────────────────┐
│       Upload to S3 + Record in DB        │
└─────────────────┬───────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ Compliance ON?  │──No──→ Mark "non-final"
        └────────┬────────┘
                 │ Yes
                 ▼
        ┌─────────────────┐
        │  Run Compliance │
        │  Pipeline (120s │
        │  timeout)       │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Record verdict  │
        │ + reasons on ad │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Emit SSE with  │
        │  pipeline_state │
        └────────┬────────┘
                 │
                 ▼
           ┌─────────┐
           │   END   │
           └─────────┘
```

### 8.2 Video V2 Two-Phase Flow

```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌──────────────────────┐
│ PHASE 1: PLANNING    │
│                      │
│ Director plans N     │
│ scenes (storyboard)  │
│         │            │
│         ▼            │
│ Generate keyframe    │
│ per scene (Imagen 4) │
│ with retry/throttle  │
│         │            │
│         ▼            │
│ Upload keyframes     │
│ to S3               │
│         │            │
│         ▼            │
│ Emit video_plan SSE │
│ Persist on task      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ USER REVIEWS         │
│ storyboard + edits   │
│ subtitles            │
│                      │
│ Clicks "Continue"    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ PHASE 2: EXECUTION   │
│                      │
│ Download keyframes   │
│ from S3              │
│         │            │
│         ▼            │
│ Veo image→video      │
│ per scene            │
│         │            │
│         ▼            │
│ Burn subtitles       │
│ (ffmpeg drawtext)    │
│         │            │
│         ▼            │
│ xfade transitions    │
│ (ffmpeg filter)      │
│         │            │
│         ▼            │
│ Generate SFX bed +   │
│ voiceover (audience- │
│ matched voice)       │
│         │            │
│         ▼            │
│ Mix audio onto video │
│ Upload final to S3   │
└──────────┬───────────┘
           │
           ▼
     ┌─────────┐
     │   END   │
     └─────────┘
```

### 8.3 Publish + Distribute Flow

```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌─────────────────┐
│ Ad generated    │
│ (status=complete)│
└────────┬────────┘
     │
     ▼
┌─────────────────┐     ┌──────────────────┐
│ Compliance      │────→│ Non-compliant?   │──→ BLOCKED (cannot publish)
│ status check    │     └──────────────────┘
└────────┬────────┘
     │ (compliant or non-final)
     ▼
┌─────────────────┐
│ User clicks     │
│ "Publish"       │
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│ status → published │
│ (idempotent)    │
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│ User clicks     │
│ "Distribute"    │
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│ Zernio POST     │
│ /api/v1/posts   │
│ publishNow=true │
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│ Record          │
│ distributed_at  │
│ + post_id on DB │
└────────┬────────┘
     │
     ▼
┌─────────┐
│   END   │
└─────────┘
```


---

## 9. Sequence Diagrams

### 9.1 Chat Generation (SSE Streaming)

```
Browser          Frontend         Backend API       Orchestrator      Media Agent       S3
  │                │                 │                  │                 │              │
  │ type message   │                 │                  │                 │              │
  │───────────────→│                 │                  │                 │              │
  │                │ POST /chat      │                  │                 │              │
  │                │────────────────→│                  │                 │              │
  │                │                 │ run_generation() │                 │              │
  │                │                 │─────────────────→│                 │              │
  │                │                 │                  │ detect_intent() │              │
  │                │   SSE: {text}   │                  │                 │              │
  │                │←────────────────│←─ stream reply ──│                 │              │
  │ show typing    │                 │                  │                 │              │
  │←───────────────│                 │                  │ generate()      │              │
  │                │                 │                  │────────────────→│              │
  │                │ SSE: {status}   │                  │                 │ upload       │
  │                │←────────────────│←─────────────────│←────────────────│─────────────→│
  │                │                 │                  │                 │              │
  │                │ SSE:{pipeline}  │                  │                 │              │
  │                │←────────────────│←─── final state ─│                 │              │
  │ show outputs   │                 │                  │                 │              │
  │←───────────────│                 │                  │                 │              │
```

### 9.2 Prompt Vector Search

```
Browser          Frontend         Backend API       Embeddings        Qdrant
  │                │                 │                  │               │
  │ type + Enter   │                 │                  │               │
  │───────────────→│                 │                  │               │
  │                │ GET /prompt-    │                  │               │
  │                │ suggestions     │                  │               │
  │                │────────────────→│                  │               │
  │                │                 │ embed_text()     │               │
  │                │                 │─────────────────→│               │
  │                │                 │ ←── 768-dim vec ─│               │
  │                │                 │                  │               │
  │                │                 │ query_points()   │               │
  │                │                 │─────────────────────────────────→│
  │                │                 │ ←── top-K results ───────────────│
  │                │ JSON response   │                  │               │
  │                │←────────────────│                  │               │
  │ show results   │                 │                  │               │
  │←───────────────│                 │                  │               │
```

---

## 10. Test Cases

### 10.1 Generation Pipeline Tests

| ID | Test Case | Input | Expected Output | Status |
|----|-----------|-------|-----------------|--------|
| G01 | Text ad generation | "Generate text caption for coffee promo" | Text output in Outputs tab, compliance badge | ✅ Pass |
| G02 | Image ad generation | "Generate image ad for matcha drink" | Image uploaded to S3, shown in gallery | ✅ Pass |
| G03 | Image with reference | Upload shoe image + "Generate ad for this product" | Generated image resembles reference | ✅ Pass |
| G04 | Video V1 (single clip) | "Generate TikTok video for energy drink" | Veo video in Output Gallery | ✅ Pass |
| G05 | Video V2 (storyboard) | Toggle V2 ON + "Generate video ad" | Storyboard with scenes → Continue → video | ✅ Pass (keyframes via Imagen 4) |
| G06 | Settings influence output | Set Chinese + Gen Z + Mandarin | Output is Mandarin, trendy tone | ✅ Pass |
| G07 | Different audience = different output | Malay Boomer vs Chinese Gen Z | Visibly different content | ✅ Pass |

### 10.2 Compliance Tests

| ID | Test Case | Input | Expected Output | Status |
|----|-----------|-------|-----------------|--------|
| C01 | Non-compliant ad shows reasons | Generate "deodorant ad showing armpits" | Red badge + "Why this verdict" panel expanded | ✅ Pass |
| C02 | Compliant ad shows low-risk | Generate safe ad | Green badge + low-risk explanation | ✅ Pass |
| C03 | Compliance skipped note | Toggle OFF + generate | Amber "Pending" + "Compliance skipped" message | ✅ Pass |
| C04 | Product context prevents hallucination | Set product="Matcha Latte" | Judge doesn't flag wrong product | ✅ Pass |

### 10.3 Publish + Distribution Tests

| ID | Test Case | Input | Expected Output | Status |
|----|-----------|-------|-----------------|--------|
| P01 | Publish button appears | Generated ad in Outputs tab | Blue Publish button visible | ✅ Pass |
| P02 | Publishing works | Click Publish | Green "Published" badge | ✅ Pass |
| P03 | Non-compliant blocked | Red-badge ad | "Blocked" notice, no Publish button | ✅ Pass |
| D01 | Distribute to TikTok | curl POST /distribute | 200 + post_id from Zernio | ✅ Pass |
| D02 | Unpublished blocked | Distribute before publish | 409 "must be published first" | ✅ Pass |
| D03 | publishNow works | Distribute with correct format | Live post (not draft) | ✅ Pass |

### 10.4 Persistence Tests

| ID | Test Case | Input | Expected Output | Status |
|----|-----------|-------|-----------------|--------|
| R01 | Ads survive refresh | Generate → F5 → reopen task | Outputs still in gallery | ✅ Pass |
| R02 | Chat history survives | Send messages → F5 | Messages restored | ✅ Pass |
| R03 | Video plan survives | Plan storyboard → F5 | Storyboard + Continue button restored | ✅ Pass |
| R04 | Settings persist | Change settings → F5 | Settings restored | ✅ Pass |

### 10.5 Infrastructure Tests

| ID | Test Case | Input | Expected Output | Status |
|----|-----------|-------|-----------------|--------|
| I01 | Delete project cleans S3 | Delete project | S3 prefix removed + DB row gone | ✅ Pass |
| I02 | Delete task cleans S3 | Delete task | Task S3 folder removed | ✅ Pass |
| I03 | Prompt search works | "coffee shop poster" | Relevant results from 14K prompts | ✅ Pass |
| I04 | Recommendations load | Open Assets page | Prompt cards shown (even empty profile) | ✅ Pass |


---

## 11. Before vs After Comparison

| Aspect | BEFORE (v1) | AFTER (v2) |
|--------|------------|-----------|
| **Ad Generation** | Single Gemini call, basic text/image | Multi-agent orchestration (4 independent agents), LangGraph pipeline |
| **Video** | FFmpeg image stitching (static frame + audio) | Veo 3 dynamic video + multi-scene storyboard with planning |
| **Compliance** | Basic check, single-pass | Full pipeline (rules + analysis + judges + bias check), conditional by audience |
| **Localization** | Hardcoded "Malaysia" + blanket prohibitions | Conditional per-ethnicity rules (Malay=halal, Chinese=OK, Indian=no-beef) |
| **Structure** | Hook→product→CTA (generic) | Hook-FIRST (scroll-stopping) then product, designed for TikTok/Reels |
| **Voice** | One fixed female voice | 12 voices: per-ethnicity + per-gender (Malay/Chinese/Indian × male/female) |
| **Image model** | Gemini Flash Lite (rate-limited) | Imagen 4 primary (separate quota) + Gemini fallback |
| **Persistence** | Lost on refresh | Generated ads, chat, storyboard plans, settings all persist in DB |
| **Distribution** | None (publish = DB flag only) | Zernio API → live posts on TikTok/Instagram |
| **Prompt Library** | 6 hardcoded template cards | 14,642 templates, vector search (Qdrant + Gemini embeddings) |
| **Settings** | Platform only | 10 fields: market, ethnicity, age, gender, language, product, category, platform, compliance, video mode |
| **UI Layout** | Gallery blocks chat | 3-tab panel: Chat / Outputs / Inspector (independent) |
| **Deletion** | DB only (S3 orphaned) | DB + S3 media purge (paginated batch delete) |
| **Code Structure** | Single `agent/` folder (mixed concerns) | `shared/` + `jusads_compliance/` + `jusads_generation/` (clean separation) |
| **Keyframe quality** | N/A | Imagen 4 @ 1048px, with character casting + multimodal consistency |
| **Audio** | Single voiceover | Per-scene SFX bed + voiceover, mixed with ducking |

---

## 12. Future Plan

### Short-term (Next Sprint)

| # | Feature | Impact |
|---|---------|--------|
| 1 | Full distribution UI (platform picker modal, caption editor) | Users can customize before posting |
| 2 | Distribution analytics (Zernio `GET /analytics/{postId}`) | Track views, likes, engagement per ad |
| 3 | Read `business_profiles` for personalized recommendations | Better prompt suggestions based on onboarding |
| 4 | Persist video plan subtitle edits across refresh | User tweaks survive page reload |

### Medium-term (Next Month)

| # | Feature | Impact |
|---|---------|--------|
| 5 | Multi-platform campaign generation | Generate one brief → output for TikTok + IG + YouTube simultaneously |
| 6 | A/B variant generation | Generate 2-3 variants of each ad for split testing |
| 7 | Scheduled publishing (via Zernio `scheduledFor`) | Queue ads for optimal posting times |
| 8 | Asset version history | Track iterations of an ad (v1 → v2 → v3) |
| 9 | Team collaboration (project_members roles) | Multiple users on one project |

### Long-term (Quarter)

| # | Feature | Impact |
|---|---------|--------|
| 10 | Performance analytics dashboard | ROI tracking, cost-per-engagement per creative |
| 11 | Auto-remediation loop | Compliance fails → auto-fix → re-check (no human intervention) |
| 12 | Singapore market expansion | Full persona + rules + voice set for SG |
| 13 | Real-time preview (live canvas render) | See video being assembled in real-time |
| 14 | Brand kit (consistent fonts, colors, logos) | Enforce brand consistency across ads |
| 15 | Shopee product feed integration | Pull product images/descriptions directly from Shopee seller center |

---

## Appendix A: Environment Variables

| Variable | Required | Used By |
|----------|----------|---------|
| `VERTEX_PROJECT_ID` | Yes | Gemini, Imagen, Veo |
| `VERTEX_LOCATION` | No (default: global) | Vertex AI |
| `SUPABASE_URL` | Yes | Database |
| `SUPABASE_KEY` | Yes | Database |
| `AWS_ACCESS_KEY_ID` | Yes | S3 |
| `AWS_SECRET_ACCESS_KEY` | Yes | S3 |
| `AWS_REGION` | Yes | S3 |
| `S3_BUCKET_NAME` | Yes | Media storage |
| `ELEVENLABS_API_KEY` | Yes | Voice/SFX |
| `QDRANT_URL` | Yes | Prompt search |
| `QDRANT_API_KEY` | Yes | Prompt search |
| `ZERNIO_API_KEY` / `ZERNIO_KEY` | For distribution | Zernio |
| `ZERNIO_ACCOUNT_TIKTOK` | For distribution | TikTok posting |
| `ZERNIO_ACCOUNT_INSTAGRAM` | For distribution | Instagram posting |

---

## Appendix B: API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/projects/{id}/tasks/{id}/chat` | Generate ads (SSE streaming) |
| POST | `/api/projects/{id}/tasks/{id}/execute-video-plan` | Render approved V2 storyboard |
| POST | `/api/projects/{id}/tasks/{id}/ads/{id}/publish` | Human approval gate |
| POST | `/api/projects/{id}/tasks/{id}/ads/{id}/distribute` | Push to social platform |
| GET | `/api/projects/{id}/tasks/{id}/generated-ads` | Fetch persisted ads |
| GET | `/api/projects/{id}/tasks/{id}/chat-history` | Fetch chat turns |
| GET | `/api/prompt-suggestions?query=...` | Vector prompt search |
| GET | `/api/prompt-recommendations` | Personalized prompt feed |
| GET | `/api/user-assets?user_email=...` | All user's generated ads |
| POST | `/api/compliance/check` | Run compliance check |
| DELETE | `/api/projects/{id}` | Delete project + S3 |
| DELETE | `/api/projects/{id}/tasks/{id}` | Delete task + S3 |

---

*End of documentation.*


---

## 13. Next Major Feature: Intelligent Remediation Engine

### Overview

Enhance post-generation editing with AI-driven tool routing. Instead of always re-generating (slow + expensive), the system intelligently picks the right editing approach:

### Architecture: AI Tool Router

```
┌──────────────────────────────────────────────────────────┐
│              Remediation Request                           │
│  "Fix the non-compliant segments" / "Change the text"     │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   AI Tool Router    │
              │   (Gemini decides)  │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐
   │  MINOR    │  │  MODERATE │  │  MAJOR    │
   │  (Edit)   │  │  (Remix)  │  │  (Regen)  │
   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
         │               │               │
         ▼               ▼               ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐
   │ CapCut API│  │ ElevenLabs│  │  Veo/     │
   │ (video)   │  │ Dubbing   │  │  Imagen   │
   │ Inpaint   │  │ (audio)   │  │  (full    │
   │ (image)   │  │ Rewrite   │  │   regen)  │
   │ Rewrite   │  │ (text)    │  │           │
   │ (text)    │  │           │  │           │
   └───────────┘  └───────────┘  └───────────┘
```

### Decision Logic

| Severity | Video | Image | Audio | Text |
|----------|-------|-------|-------|------|
| **Minor** (subtitle fix, small area) | CapCut: add/edit text overlay | Inpaint: mask + regenerate area | ElevenLabs: re-dub specific segment | Gemini: rewrite flagged phrase |
| **Moderate** (scene change, tone shift) | CapCut: trim + replace scene + re-transition | Imagen: regenerate with constraints | ElevenLabs: voice clone + full re-read | Gemini: full copy rewrite |
| **Major** (complete redo needed) | Veo: re-generate from keyframe | Imagen: full regeneration | ElevenLabs: new VO from scratch | Gemini: complete new copy |

### Audio Remediation Plan (ElevenLabs)

| Capability | API | Use Case |
|-----------|-----|----------|
| **Voice Cloning** | `POST /v1/voices/add` | Clone the brand's voice for consistent future ads |
| **Dubbing** | `POST /v1/dubbing` | Re-dub specific segments with the cloned voice |
| **Text-to-Speech** | `POST /v1/text-to-speech/{voice_id}` | Generate replacement narration |
| **Sound Effects** | `POST /v1/sound-generation` | Replace/add ambient SFX |
| **Audio Isolation** | `POST /v1/audio-isolation` | Extract voice from background for editing |

**Ref:** https://elevenlabs.io/docs/eleven-api/guides/cookbooks

### Video Remediation Plan (CapCut API)

| Capability | Use Case |
|-----------|----------|
| **Add text overlay** | Fix/add subtitles, CTAs |
| **Trim/cut** | Remove non-compliant segment |
| **Speed ramp** | Adjust pacing of specific scenes |
| **Replace audio** | Swap voiceover/music bed |
| **Add transitions** | Smooth scene changes |
| **Filter/color grade** | Match brand aesthetic |
| **Template apply** | Apply CapCut template to raw footage |

**Ref:** https://github.com/ashreo/CapCutAPI (Open CapCut API)

### Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| R1 | AI Tool Router — Gemini classifies severity + picks tool | 1 sprint |
| R2 | ElevenLabs voice cloning + per-segment dubbing | 1 sprint |
| R3 | CapCut API integration for video editing (text, trim, transitions) | 2 sprints |
| R4 | Unified remediation UI (show before/after, approve changes) | 1 sprint |

### Key Design Decisions

1. **AI decides the tool** — the user doesn't pick CapCut vs Veo; the AI analyzes what needs fixing and routes to the cheapest/fastest option that can handle it.
2. **Voice cloning is persistent** — once you clone your brand voice, it's stored and reused across all future ads (no re-cloning needed).
3. **CapCut for edits, Veo for generation** — CapCut handles post-production (what an editor would do); Veo handles raw content creation (what a camera would do).
4. **Remediation is non-destructive** — original is always preserved; the edit creates a new version linked via `parent_ad_id`.
