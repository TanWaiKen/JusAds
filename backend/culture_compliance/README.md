# Culture Compliance Pipeline

Content compliance evaluation for Malaysian and Singaporean advertising, powered by a LangGraph orchestration pipeline. Evaluates text, image, and video content against both **regulatory guidelines** (MCMC for Malaysia, IMDA/ASAS for Singapore) and **cultural guidelines** (Malay, Chinese, Indian ethnic sensitivities).

## Tech Stack

| Component | Technology |
|---|---|
| Orchestration | LangGraph StateGraph |
| Embeddings | Cohere embed-v4 (1024-dim) via AWS Bedrock |
| LLM Evaluation | Amazon Nova Pro via AWS Bedrock Inference Profile |
| Video Understanding | TwelveLabs Pegasus 1.2 via AWS Bedrock |
| Vector Store | Qdrant Cloud |
| Deployment | AWS Lambda + API Gateway |

---

## Project Structure

```
culture_compliance/
├── config.py                   # Centralised env var config
├── orchestrator.py             # LangGraph pipeline builder + run_pipeline()
├── handler.py                  # AWS Lambda entry point
├── embeddings.py               # Cohere embed-v4 wrapper
├── scoring.py                  # Scoring formula, severity mapping
├── qdrant_store.py             # Qdrant collection management + retrieval
├── ingest.py                   # Ingest regulatory guidelines CSV → Qdrant
├── ingest_cultural.py          # Ingest cultural guidelines CSV → Qdrant
├── cli.py                      # CLI for local testing
│
├── models/
│   ├── schemas.py              # Pydantic models: ContentSubmission, PipelineState, ComplianceResult
│   └── cultural_schemas.py     # Pydantic models: GuidelineEntry, Ethnicity, CulturalCategory
│
├── nodes/                      # LangGraph pipeline steps (in execution order)
│   ├── step1_routing.py        # Content type validation, market resolution, ethnicity/age validation
│   ├── step2_video_analysis.py # TwelveLabs Pegasus video understanding
│   ├── step3_image_analysis.py # Nova Pro vision + OCR
│   ├── step4_text_analysis.py  # Text content preparation
│   ├── step5_guideline_retrieval.py  # Combined regulatory + cultural RAG (top 50)
│   ├── step6_compliance_evaluation.py # LLM compliance scoring
│   └── step7_result_formatting.py    # Result formatting + error handling
│
├── services/
│   ├── vision.py               # Nova Pro image analysis
│   ├── ocr.py                  # Textract OCR
│   ├── transcriber.py          # Amazon Transcribe audio-to-text
│   └── frame_extractor.py      # Video frame extraction
│
├── generators/                 # Hypothesis PBT strategies
│   ├── submissions.py          # ContentSubmission strategies
│   ├── results.py              # ComplianceResult strategies
│   ├── cultural_guidelines.py  # GuidelineEntry strategies
│   └── csv_rows.py             # Valid/invalid CSV row strategies
│
├── data/
│   ├── mcmc_guidelines.csv             # Malaysian MCMC regulatory guidelines
│   ├── singapore_imda_asas_guidelines.csv  # Singapore IMDA/ASAS guidelines
│   └── cultural_guidelines.csv         # Ethnic cultural guidelines (Malay/Chinese/Indian)
│
└── tests/
    ├── test_cultural_properties.py     # 13 PBT properties for cultural guidelines
    ├── test_data_model_properties.py   # PBT for core data models
    ├── test_scoring_properties.py      # PBT for scoring formula
    ├── test_orchestrator.py            # Orchestrator graph structure + retry logic
    ├── test_compliance_evaluation.py   # Step 6 unit tests
    ├── test_result_formatting.py       # Step 7 unit tests
    └── integration/                    # End-to-end tests (require live Qdrant)
```

---

## Pipeline Flow

```
ContentSubmission
      │
      ▼
step1_routing          ← validates content_type, market, target_ethnicity, target_age_group
      │
      ├─ text  ──► step4_text_analysis
      ├─ image ──► step3_image_analysis  (Nova Pro vision + Textract OCR)
      └─ video ──► step2_video_analysis  (TwelveLabs Pegasus)
                        │
                        ▼
               step5_guideline_retrieval  ← queries regulatory + cultural Qdrant collections (top 50)
                        │
                        ▼
               step6_compliance_evaluation  ← Nova Pro LLM scores against both guideline types
                        │
                        ▼
               step7_result_formatting  ← builds ComplianceResult with severity-sorted violations
                        │
                        ▼
                 ComplianceResult
```

---

## Setup

### 1. Environment variables

Copy `.env.example` to `.env` and fill in your values:

```env
# AWS Bedrock
AWS_REGION_LLM=ap-southeast-1
AWS_REGION_EMBED=ap-southeast-1
EMBED_MODEL_ID=global.cohere.embed-v4:0
LLM_MODEL_ID=apac.amazon.nova-pro-v1:0
VISION_MODEL_ID=apac.amazon.nova-pro-v1:0
VIDEO_MODEL_ID=global.twelvelabs.pegasus-1-2-v1:0

# Qdrant
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_TOP_K=50

# S3 (for video async processing)
TRANSCRIBE_S3_BUCKET=your-transcribe-temp-bucket
COMPLIANCE_RESULTS_BUCKET=your-results-bucket
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Ingest regulatory guidelines

Run from the `backend/` directory (one level up from `culture_compliance/`):

```bash
cd backend/

# Malaysia (MCMC)
python -m culture_compliance.ingest --market malaysia

# Singapore (IMDA/ASAS)
python -m culture_compliance.ingest --market singapore

# Recreate collection from scratch
python -m culture_compliance.ingest --market malaysia --recreate
```

### 4. Ingest cultural guidelines

```bash
cd backend/

# Ingest all ethnic cultural guidelines (Malay, Chinese, Indian)
python -m culture_compliance.ingest_cultural

# Recreate the cultural-guidelines collection
python -m culture_compliance.ingest_cultural --recreate
```

---

## API

### Request

```
POST /evaluate
Content-Type: application/json
```

```json
{
  "content": "Your ad copy, image description, or S3 video URL",
  "content_type": "text",
  "market": "malaysia",
  "target_ethnicity": "malay",
  "target_age_group": "all_ages"
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `content` | string | ✅ | Ad text, base64 image, or S3 URI |
| `content_type` | string | ✅ | `"text"`, `"image"`, `"video"` |
| `market` | string | ✅ | `"malaysia"`, `"singapore"` |
| `target_ethnicity` | string | ❌ | `"malay"`, `"chinese"`, `"indian"`, `"all"` (default: `"all"`) |
| `target_age_group` | string | ❌ | `"all_ages"`, `"adults_only"`, `"children"` (default: `"all_ages"`) |

### Response (text / image — synchronous)

```json
{
  "content_type": "text",
  "market": "malaysia",
  "risk_level": "Medium",
  "score": 62,
  "high_risk_indicators": [
    {
      "phrase": "apply directly to skin",
      "char_offset": 45,
      "category": "Sexual/Explicit",
      "severity": "Moderate",
      "guideline_source": "cultural"
    }
  ],
  "explanation": "The ad contains suggestive product application language...",
  "suggestion": "Rephrase to focus on product benefits without physical demonstration.",
  "processing_metadata": {
    "pipeline_duration_ms": 1240,
    "models_used": ["apac.amazon.nova-pro-v1:0"],
    "market": "malaysia"
  },
  "warnings": []
}
```

### Response (video — asynchronous)

```json
{
  "message": "Video compliance evaluation accepted for processing",
  "request_id": "a1b2c3d4-...",
  "result_location": "s3://compliance-results/results/a1b2c3d4-....json"
}
```

---

## Running Tests

Run from the `backend/` directory:

```bash
# All tests
python -m pytest culture_compliance/tests/ -v --timeout=120

# Cultural property tests only (13 PBT properties)
python -m pytest culture_compliance/tests/test_cultural_properties.py -v --timeout=120

# All unit tests, skip integration
python -m pytest culture_compliance/tests/ --ignore=culture_compliance/tests/integration -q --timeout=60

# With Hypothesis statistics
python -m pytest culture_compliance/tests/test_cultural_properties.py -v --hypothesis-show-statistics
```

**Expected:** 475 passed, 1 known pre-existing failure in `tests/integration/test_ingestion.py` (vector dimension mismatch from a legacy collection — not a regression).

---

## Guideline Collections

| Collection | Market | Content |
|---|---|---|
| `mcmc-guidelines` | Malaysia | MCMC regulatory rules |
| `singapore-imda-asas-guidelines` | Singapore | IMDA/ASAS regulatory rules |
| `cultural-guidelines` | MY + SG | Ethnic cultural rules (Malay, Chinese, Indian) |

All collections use **Cohere embed-v4** (1024-dim, Cosine distance). The pipeline retrieves **top 50** combined results per evaluation.

---

## Scoring

```
score = max(0, round(100 - Σ(category_weight × severity_multiplier)))
```

| Severity | Multiplier |
|---|---|
| Minor | 0.25 |
| Moderate | 0.60 |
| Severe | 1.00 |

| Risk Level | Score Range |
|---|---|
| Low | ≥ 75 |
| Medium | 40 – 74 |
| High | < 40 |

Cultural guideline severity maps to compliance severity: `high → Severe`, `medium → Moderate`, `low → Minor`. The same scoring formula applies to both regulatory and cultural violations.
