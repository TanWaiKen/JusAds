# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**JusAds** is a multi-modal advertising compliance platform with three main components:
1. **JusAds Text Compliance** - Simplified text-only compliance checker (Malaysia focus, easy to use)
2. **Culture Compliance Pipeline** - Full multi-modal compliance evaluation (text, image, video) with LangGraph
3. **Audio Ads Generator** - Voice ad creation pipeline using Gemini and ElevenLabs

## Repository Structure

```
JusAds/
├── backend/
│   ├── jusads_text_compliance/  # Simple text compliance checker (Malaysia, no LangGraph)
│   ├── culture_compliance/      # Full multi-modal pipeline (LangGraph + AWS)
│   └── audio_ads_aws/           # Voice ad generation (Gemini + ElevenLabs)
└── frontend/                    # React + Vite dashboard (TypeScript)
```

---

## Backend: JusAds Text Compliance (New - Simplified)

**Location:** `backend/jusads_text_compliance/`

### Purpose

Simplified text-only compliance checker designed for **ease of use and transparency**. This is the recommended starting point for text compliance evaluation. Unlike `culture_compliance/`, this module:
- ✅ No LangGraph complexity - simple function calls
- ✅ Easy to spot-check rules (personas exported to JSON)
- ✅ Reuses existing Qdrant collections (no duplicate data)
- ✅ Malaysia-first focus (Singapore supported)
- ✅ Clear evaluation flow with detailed logging

### Tech Stack
- **LLM:** Google Gemini 2.0 Flash (evaluation)
- **Embeddings:** Google text-embedding-004 (768-dim)
- **Vector Store:** Qdrant Cloud (reuses `culture_compliance` collections)
- **No orchestration:** Direct Python function calls

### Running Commands

**From `backend/` directory:**

```bash
# Export personas from Qdrant to local JSON (one-time)
python -m jusads_text_compliance.export_personas

# Check ad text compliance (default: Malaysia, all ethnicities)
python -m jusads_text_compliance.cli --text "Try our new whitening cream today!"

# Target specific ethnicity
python -m jusads_text_compliance.cli \
  --text "Win big at our casino!" \
  --ethnicity malay

# Show retrieved rules in output
python -m jusads_text_compliance.cli \
  --text "Your ad copy here" \
  --ethnicity chinese \
  --show-rules

# JSON output format
python -m jusads_text_compliance.cli --text "Your ad copy" --json

# Verbose logging (DEBUG level)
python -m jusads_text_compliance.cli --text "Your ad copy" --verbose
```

### Environment Variables

Required in `.env` at `backend/.env`:

```env
# Google Gemini
GOOGLE_API_KEY=your-google-api-key

# Qdrant (reuse from culture_compliance)
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key

# Optional: Customize retrieval
TOP_K_REGULATORY=10
TOP_K_CULTURAL=10
```

### Key Files

- `text_checker.py` - Main compliance checker class
- `qdrant_client.py` - Thin wrapper around Qdrant collections
- `embeddings.py` - Gemini text-embedding-004 wrapper
- `cli.py` - Command-line interface
- `export_personas.py` - Export personas to JSON for spot-checking
- `personas/` - Exported persona JSON files (created by export script)

### Python API Usage

```python
from jusads_text_compliance.text_checker import TextComplianceChecker

checker = TextComplianceChecker()

result = checker.check_compliance(
    ad_text="Try our new whitening cream today!",
    market="malaysia",
    ethnicity="malay",
    age_group="all_ages",
)

print(f"Risk Level: {result['risk_level']}")  # Low/Medium/High
print(f"Score: {result['score']}/100")
print(f"Violations: {len(result['violations'])}")
```

### When to Use This vs `culture_compliance/`

Use `jusads_text_compliance/` when:
- You only need text compliance (no images/videos)
- You want simple, transparent code
- You need to easily spot-check rules and personas
- You're learning the compliance system

Use `culture_compliance/` when:
- You need multi-modal support (image, video)
- You need AWS Lambda deployment
- You need LangGraph orchestration features
- You need the full production pipeline

---

## Backend: Culture Compliance Pipeline (Full-Featured)

**Location:** `backend/culture_compliance/`

### Tech Stack
- **Orchestration:** LangGraph StateGraph (conditional routing, retry logic)
- **LLM/Vision:** Amazon Nova Pro via AWS Bedrock Inference Profile
- **Video Understanding:** TwelveLabs Pegasus 1.2 via AWS Bedrock
- **Embeddings:** Cohere embed-v4 (1024-dim) via AWS Bedrock
- **Vector Store:** Qdrant Cloud (regulatory + cultural guideline collections)
- **Deployment:** AWS Lambda + API Gateway (sync for text/image, async for video)

### Key Architecture Patterns

1. **LangGraph State Machine** (`orchestrator.py`)
   - Content type routing (text → step4, image → step3, video → step2)
   - Conditional edges based on pipeline state errors
   - Retry wrapper with exponential backoff for transient AWS errors
   - **Video v3 path:** content_routing → market_resolution → guideline_retrieval → video_processing → result_formatting (skips step6, single-model approach)
   - **Text/Image v2 path:** content_routing → processing → market_resolution → guideline_retrieval → compliance_evaluation → result_formatting

2. **Dual Guideline System** (`step5_guideline_retrieval.py`)
   - Regulatory guidelines: MCMC (Malaysia), IMDA/ASAS (Singapore)
   - Cultural guidelines: Ethnic sensitivities (Malay, Chinese, Indian)
   - Combined RAG retrieval (top 50 results from both collections)
   - Filtered by `target_ethnicity` and `target_age_group` metadata

3. **Lambda Handler Patterns** (`handler.py`)
   - Sync execution for text/image (55s timeout)
   - Async execution for video (self-invocation + S3 result storage)
   - /tmp cleanup after every invocation (stateless design)
   - Payload size validation (1 MB max)

4. **Pydantic Schema Validation** (`models/schemas.py`)
   - `ContentSubmission` input model with `target_ethnicity` and `target_age_group` fields
   - `PipelineState` TypedDict for LangGraph node communication
   - `ComplianceResult` output with `high_risk_indicators` (phrase, category, severity, guideline_source)

### Running Commands

**From `backend/` directory:**

```bash
# Ingest regulatory guidelines into Qdrant
python -m culture_compliance.ingest --market malaysia
python -m culture_compliance.ingest --market singapore

# Ingest cultural guidelines
python -m culture_compliance.ingest_cultural

# Ingest cultural personas (for video v3 pipeline)
python -m culture_compliance.ingest_personas

# Run CLI locally (requires .env with AWS credentials + Qdrant config)
python -m culture_compliance.cli \
  --content "Your ad text here" \
  --content-type text \
  --market malaysia \
  --ethnicity malay \
  --age-group all_ages

# Test image compliance
python -m culture_compliance.cli \
  --content path/to/image.png \
  --content-type image \
  --market singapore

# Test video compliance (reads local file, extracts frames)
python -m culture_compliance.cli \
  --content path/to/video.mp4 \
  --content-type video \
  --market malaysia
```

**Testing:**

```bash
# All tests (from backend/)
python -m pytest culture_compliance/tests/ -v --timeout=120

# Unit tests only (skip integration)
python -m pytest culture_compliance/tests/ --ignore=culture_compliance/tests/integration -q --timeout=60

# Cultural property-based tests (13 PBT properties)
python -m pytest culture_compliance/tests/test_cultural_properties.py -v --hypothesis-show-statistics
```

### Environment Variables

Required in `.env` at `backend/culture_compliance/.env`:

```env
# AWS Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_LLM=ap-southeast-1
EMBED_MODEL_ID=global.cohere.embed-v4:0
LLM_MODEL_ID=apac.amazon.nova-pro-v1:0
VISION_MODEL_ID=apac.amazon.nova-pro-v1:0
VIDEO_MODEL_ID=global.twelvelabs.pegasus-1-2-v1:0

# Video compliance (v3 single-model)
VIDEO_COMPLIANCE_MODEL=claude  # or "pegasus"
CLAUDE_VIDEO_MODEL_ID=apac.anthropic.claude-sonnet-4-20250514-v1:0

# Qdrant
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=...
QDRANT_TOP_K=50

# S3 (for async video processing)
TRANSCRIBE_S3_BUCKET=jusads-transcribe-temp
COMPLIANCE_RESULTS_BUCKET=compliance-results
```

### Key Files

- `orchestrator.py` - LangGraph pipeline builder, retry logic, routing functions
- `handler.py` - AWS Lambda entry point, sync/async routing, /tmp cleanup
- `config.py` - Centralized env var config (all secrets loaded here)
- `cli.py` - Local testing CLI (mirrors Lambda handler schema)
- `models/schemas.py` - Pydantic models for submission, state, and result
- `models/cultural_schemas.py` - Cultural guideline data models
- `nodes/step5_guideline_retrieval.py` - Combined regulatory + cultural RAG
- `nodes/step6_compliance_evaluation.py` - LLM scoring against guidelines
- `scoring.py` - Severity-weighted scoring formula

### Testing Strategy

- **Property-Based Testing (Hypothesis):** `test_cultural_properties.py` (13 properties)
- **Integration Tests:** Require live Qdrant connection (in `tests/integration/`)
- **Known Issue:** 1 pre-existing failure in `test_ingestion.py` (legacy vector dimension mismatch, not a regression)

---

## Backend: Audio Ads Generator

**Location:** `backend/audio_ads_aws/`

### Tech Stack
- **LLM:** Google Gemini (via `gemini_client.py`)
- **Voice Synthesis:** ElevenLabs (TTS + SFX API)
- **Audio Processing:** pydub (mixing, overlay)

### Pipeline Flow

```
Step 1: Product Idea Enhancement (Gemini) → refined concept
Step 2: Script Generation (Gemini) → 4-scene JSON with SFX prompts
Step 3: Sound Effects (ElevenLabs SFX API) → per-scene audio
Step 4: Voice Over (ElevenLabs TTS) + Final Mix (pydub) → MP3
```

### Running Commands

**From `backend/audio_ads_aws/` directory:**

```bash
python main.py \
  --idea "FitPulse AI smart wristband" \
  --mood "energetic" \
  --audience "young professionals" \
  --language ms \
  --gender male \
  --country my \
  --output output/final_ad.mp3
```

### Environment Variables

Required in `.env` at `backend/audio_ads_aws/.env`:

```env
ELEVENLABS_API_KEY=...
GOOGLE_API_KEY=...

# Voice mapping (example for Malaysian Malay male)
VOICE_MY_MS_MALE=<elevenlabs-voice-id>
VOICE_MY_MS_FEMALE=<elevenlabs-voice-id>
```

### Key Files

- `main.py` - Pipeline orchestration (4 steps + final mix)
- `step1_product_idea.py` - Gemini prompt for product enhancement
- `step2_script_generation.py` - Gemini 4-scene JSON script generation
- `step3_sound_effects.py` - ElevenLabs SFX generation per scene
- `step4_voiceover.py` - ElevenLabs TTS per scene
- `utils/elevenlabs_utils.py` - Voice ID resolution, audio mixing
- `utils/bedrock_client.py` - AWS Bedrock client for LLM fallback (if needed)

---

## Frontend

**Location:** `frontend/`

### Tech Stack
- **Framework:** React 19 + Vite 8 + TypeScript 6
- **Routing:** React Router 7
- **Styling:** Tailwind CSS 4 + shadcn/ui components
- **Auth:** AWS Cognito (OIDC via `oidc-client-ts`)
- **Theme:** next-themes (light/dark mode)

### Running Commands

```bash
cd frontend/

# Install dependencies
npm install

# Start dev server (default: http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint TypeScript/React
npm run lint
```

### Key Architecture

1. **Routing** (`App.tsx`)
   - Landing page: `/`
   - OAuth callback: `/callback` (Cognito redirect)
   - Protected dashboard: `/dashboard/*` (wrapped in `ProtectedRoute`)

2. **Protected Routes** (`components/protected-route.tsx`)
   - Checks `isAuthenticated` from `AuthProvider`
   - Redirects to landing page if not authenticated

3. **Auth Provider** (`lib/authProvider.tsx`)
   - Manages Cognito OIDC flow
   - Provides `login()`, `logout()`, `isAuthenticated` context

4. **Dashboard Pages** (`pages/dashboard.tsx` shell)
   - `/dashboard` - Home
   - `/dashboard/campaigns` - Campaign management
   - `/dashboard/assets` - Asset library
   - `/dashboard/compliance` - Compliance evaluation UI
   - `/dashboard/profile` - User profile

### Key Files

- `App.tsx` - React Router setup, route definitions
- `main.tsx` - React root, StrictMode wrapper
- `lib/authProvider.tsx` - Cognito OIDC authentication
- `components/protected-route.tsx` - Route guard wrapper
- `components/callback-handler.tsx` - OAuth callback processor
- `pages/compliance.tsx` - Culture compliance UI (connects to backend)

### shadcn/ui Components

Pre-configured UI components in `components/ui/`. To add new components:

```bash
npx shadcn@latest add <component-name>
```

---

## Development Workflow

### Git Branches

- **main** - Production branch (PR target)
- **feature/culture_compliance** - Current working branch (culture compliance pipeline v2/v3)
- **feature/audio-ad-generation** - Audio ads pipeline (merged)

### Committing Changes

When creating commits, follow the existing style:
- Prefix: `feat()`, `fix()`, `docs()`, `test()`, `refactor()`
- Scope: component name (e.g., `feat(culture_compliance):`)
- Include co-authorship tag: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`

### Environment Setup

1. **Backend Python:** Requires Python 3.11+ and `uv` package manager
2. **Frontend Node:** Requires Node.js 18+ and npm
3. **AWS Credentials:** Set in `.env` or via AWS CLI config
4. **Qdrant Cloud:** Free tier cluster (requires QDRANT_URL + QDRANT_API_KEY)

---

## Common Patterns

### Adding a New LangGraph Node

1. Create `backend/culture_compliance/nodes/stepN_<name>.py`
2. Implement function signature: `def my_node(state: PipelineState) -> PipelineState`
3. Append errors to `state.errors` on failure (don't raise exceptions)
4. Register in `orchestrator.py`: `graph.add_node("my_node", my_node)`
5. Add conditional routing logic for error handling

### Adding a New Guideline Collection

1. Create CSV in `backend/culture_compliance/data/<name>.csv`
2. Add ingestion script in `backend/culture_compliance/ingest_<name>.py`
3. Update `config.py` with collection name config
4. Run ingestion: `python -m culture_compliance.ingest_<name>`

### Adding a New Compliance Category

1. Update `VIOLATION_CATEGORIES` in `models/schemas.py`
2. Update category weights in `scoring.py`
3. Regenerate test cases: `python -m pytest --hypothesis-seed=<new>`

### Frontend API Integration

The compliance frontend (`pages/compliance.tsx`) expects the backend Lambda to be deployed at a configured API Gateway URL. Update the endpoint in the component or use environment variables.

---

## Known Issues

1. **Integration Test Failure:** `tests/integration/test_ingestion.py` has 1 known failure due to legacy vector dimension mismatch (not a regression)
2. **Video Processing:** Async Lambda invocation requires proper IAM permissions for self-invocation and S3 writes
3. **Qdrant Collections:** Must be created before first use (run ingestion scripts)

---

## Performance Notes

- **Text/Image Compliance:** Typically completes in 1-2 seconds (synchronous Lambda)
- **Video Compliance:** Typically completes in 30-60 seconds (asynchronous Lambda + S3)
- **Qdrant Retrieval:** Top 50 results optimized with metadata filtering (ethnicity, age group)
- **Retry Logic:** Max 2 retries with exponential backoff for Bedrock throttling

---

## Testing Before Deployment

1. **Backend:** Run full test suite from `backend/` directory
2. **Frontend:** Run `npm run build` to verify TypeScript compilation
3. **Integration:** Test CLI locally with sample content before Lambda deployment
4. **Lambda:** Test async video flow with a real S3 video URI

---

## Architecture Decisions

- **Why LangGraph?** Explicit state management, conditional routing, and retry logic without complex control flow
- **Why Dual Guideline Collections?** Separate regulatory (legal) vs. cultural (ethnic) concerns for granular filtering
- **Why Async Video?** Video processing exceeds API Gateway 29s timeout; async pattern with S3 results avoids client blocking
- **Why Pydantic Everywhere?** Type safety at API boundary, Lambda event parsing, and test generation (Hypothesis strategies)
