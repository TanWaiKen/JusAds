# JusAds Text Compliance Checker

Simplified text-only compliance checker for Malaysian advertising. This module provides a clean, straightforward API for evaluating ad copy against regulatory and cultural guidelines.

## Why This Module?

The existing `culture_compliance/` module is feature-complete but complex (LangGraph orchestration, multi-modal support). This module focuses on **simplicity and transparency** for text compliance:

- ✅ No LangGraph - just simple function calls
- ✅ Easy to spot-check rules (personas exported to JSON)
- ✅ Reuses existing Qdrant collections (no duplicate data)
- ✅ Clear evaluation flow: embed → retrieve → evaluate
- ✅ Human-readable output with violation details

## Architecture

```
Text Input
    ↓
1. Generate Embedding (Gemini text-embedding-004)
    ↓
2. Retrieve Regulatory Rules (Qdrant: mcmc-guidelines)
    ↓
3. Retrieve Cultural Guidelines (Qdrant: cultural-guidelines, filtered by ethnicity)
    ↓
4. Retrieve Persona (Qdrant: cultural-personas)
    ↓
5. Evaluate with LLM (Gemini 2.0 Flash)
    ↓
Compliance Result (risk_level, score, violations, suggestions)
```

## Setup

### 1. Environment Variables

Create `.env` in `backend/` directory:

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

### 2. Install Dependencies

```bash
cd backend/
pip install google-genai qdrant-client python-dotenv
```

### 3. Export Personas (Optional)

Export personas from Qdrant to local JSON for easy spot-checking:

```bash
python -m jusads_text_compliance.export_personas
```

This creates `personas/all_personas.json` with all cultural personas organized by market and ethnicity.

## Usage

### CLI

```bash
cd backend/

# Basic check (default: malaysia, all ethnicities)
python -m jusads_text_compliance.cli --text "Try our new whitening cream today!"

# Specific ethnicity
python -m jusads_text_compliance.cli \
  --text "Win big at our casino!" \
  --ethnicity malay

# Show retrieved rules
python -m jusads_text_compliance.cli \
  --text "Your ad copy here" \
  --ethnicity chinese \
  --show-rules

# JSON output
python -m jusads_text_compliance.cli \
  --text "Your ad copy" \
  --json

# Verbose logging
python -m jusads_text_compliance.cli \
  --text "Your ad copy" \
  --verbose
```

### Python API

```python
from jusads_text_compliance.text_checker import TextComplianceChecker

checker = TextComplianceChecker()

result = checker.check_compliance(
    ad_text="Try our new whitening cream today!",
    market="malaysia",
    ethnicity="malay",
    age_group="all_ages",
)

print(f"Risk Level: {result['risk_level']}")
print(f"Score: {result['score']}/100")
print(f"Violations: {len(result['violations'])}")
```

## Output Format

```json
{
  "ad_text": "Your ad copy",
  "market": "malaysia",
  "ethnicity": "malay",
  "age_group": "all_ages",
  "risk_level": "Medium",
  "score": 65,
  "violations": [
    {
      "description": "[Religious Sensitivity] (Severity: Severe, Source: cultural): ..."
    }
  ],
  "explanation": "The ad contains language that may be offensive...",
  "suggestion": "Rephrase the ad to avoid references to...",
  "persona_used": "I am a Malay Muslim viewer...",
  "regulatory_rules_count": 10,
  "cultural_rules_count": 8,
  "processing_time_ms": 1250
}
```

## Spot-Checking Rules

### View Personas

After running `export_personas.py`, open:
- `personas/malaysia_personas.json` - Malaysian cultural personas (Malay, Chinese, Indian)
- `personas/singapore_personas.json` - Singaporean cultural personas

### View Rules in Qdrant

Use the Qdrant web UI or query directly:
- Collection: `mcmc-guidelines` (regulatory)
- Collection: `cultural-guidelines` (cultural, filterable by ethnicity)

## Scoring Logic

```
Start at 100 points, deduct for violations:

Regulatory:
- Severe:   -30 points
- Moderate: -20 points
- Minor:    -10 points

Cultural:
- Severe:   -25 points
- Moderate: -15 points
- Minor:    -8 points

Risk Levels:
- Low:    75-100 points
- Medium: 40-74 points
- High:   0-39 points
```

## Comparison with `culture_compliance/`

| Feature | `jusads_text_compliance/` | `culture_compliance/` |
|---------|--------------------------|----------------------|
| Text compliance | ✅ Simplified | ✅ Full-featured |
| Image compliance | ❌ Not supported | ✅ Supported |
| Video compliance | ❌ Not supported | ✅ Supported |
| Orchestration | Simple functions | LangGraph StateGraph |
| Spot-check rules | ✅ Easy (JSON export) | ⚠️ Requires Qdrant query |
| AWS Lambda ready | ❌ Not yet | ✅ Yes |
| Learning curve | Low | High |

## Future Enhancements

- [ ] Add batch processing for multiple ads
- [ ] Export rules to CSV for offline review
- [ ] Add caching for repeated queries
- [ ] Web API endpoint (FastAPI)
- [ ] Integration with frontend dashboard

## Troubleshooting

### "Failed to initialize checker"
- Check that `QDRANT_URL`, `QDRANT_API_KEY`, and `GOOGLE_API_KEY` are set in `.env`
- Verify Qdrant collections exist (run ingestion scripts from `culture_compliance/`)

### "No persona found"
- Run `python -m culture_compliance.ingest_personas` to populate the persona collection

### "Empty results"
- Verify Qdrant collections are populated
- Check network connectivity to Qdrant Cloud

## License

Part of the JusAds project.
