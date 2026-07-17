# JusAds Compliance Issues — Complete Fix Guide

This document lists all issues identified in the compliance system and the changes needed to fix them.

---

## ✅ FIXED — Persona Lookup Failure

**Files Changed:**
- `backend/jusads_compliance/rules_client.py`

**Root Cause:**
The query looked for `age_group='all_ages'` but the DB has `age_group='base'`. Query returned empty, persona was never loaded.

**What was fixed:**
Changed `get_persona()` to fetch all rows for market+ethnicity in one query, then apply a 3-level fallback:
1. Exact match on requested age_group
2. Fallback to `age_group='base'`
3. Fallback to any available row

**Result:** Persona data now loads correctly for every compliance check. Log no longer shows "No persona found" warnings.

---

## ✅ FIXED — Double Pipeline Execution

**Files Changed:**
- `backend/routes/compliance.py`

**Root Cause:**
The route handler called `_tracker.start_step()` and `_tracker.complete_step()` around each node. But each node function in `compliance_pipeline.py` also calls those same tracker methods internally. Result: every step was recorded twice in the database.

**What was fixed:**
Removed `_tracker` calls from the route loop. The nodes already track their own progress internally. The route now only emits SSE events for the frontend.

**Result:** Each pipeline node now executes exactly once. Database logs are clean.

---

## 🔴 REMAINING BACKEND ISSUES

### 1. Empty Text Returns Fake 100% Critical Score

**File:** `backend/jusads_compliance/compliance_pipeline.py`  
**Function:** `main_brain_analysis` (line ~330)

**Problem:**
When `text_input` is empty, the code returns:
```python
result["risk_percentage"] = 100
result["risk_level"] = "Critical"
result["explanation"] = error_msg
```

This is misleading — an empty input shouldn't have a "risk score" at all.

**Fix Needed:**
```python
if not text_input or not text_input.strip():
    error_msg = "No text content provided for evaluation. Please enter ad copy."
    _tracker.fail_step(task_id, step_name, error_msg)
    result["error"] = error_msg
    result["evaluation_status"] = "incomplete"  # NEW FIELD
    result["risk_percentage"] = 0
    result["risk_level"] = "Unknown"
    result["compliance_verdict"] = "incomplete_evaluation"  # NEW FIELD
    result["explanation"] = error_msg
    return {"result": result}
```

---

### 2. Research Agent Output Never Reaches Main Analysis

**File:** `backend/jusads_compliance/compliance_pipeline.py`  
**Function:** `legal_research_agent` saves to `result["_research_context"]`  
**Function:** `main_brain_analysis` never reads it

**Problem:**
The legal research agent runs Tavily searches and stores the result in `result["_research_context"]`. But `main_brain_analysis` never injects this into the compliance prompts. The research is silently dropped.

**Fix Needed in `main_brain_analysis`:**
```python
# After fetching rules and persona
research_context = result.get("_research_context", "No additional regulatory research available.")

# Then inject it into all prompt format calls:
prompt = TEXT_COMPLIANCE_PROMPT.format(
    ...
    research_context=research_context,  # ADD THIS LINE
)
```

**Fix Needed in Prompt Templates:**
All prompt files need a `{research_context}` placeholder added:
- `shared/prompts/text_compliance.md`
- `shared/prompts/image_compliance.md`
- `shared/prompts/audio_compliance.md`
- `shared/prompts/video_compliance.md`

Add this section to each:
```markdown
### Research-Augmented Regulatory Context
{research_context}
```

---

### 3. Gambling/Casino Content Skips Research

**File:** `backend/jusads_compliance/compliance_pipeline.py`  
**Function:** `legal_research_agent` (line ~420)

**Problem:**
The function asks Gemini "Does this need research?" and if Gemini says `"NO_RESEARCH_NEEDED"`, research is skipped. Gemini can miss gambling/casino content and skip research, allowing the content to pass.

**Fix Needed:**
Add a hard-coded pre-check before the LLM decision:

```python
# BEFORE the decision_prompt call, add:
HIGH_RISK_KEYWORDS = [
    "gambling", "casino", "lottery", "betting", "slot machine",
    "poker", "blackjack", "roulette", "online casino",
    "alcohol", "liquor", "beer", "wine", "tobacco", "cigarette",
    "cryptocurrency", "crypto", "bitcoin", "nft", "firearms", "gun"
]

content_lower = content_to_analyze.lower()
force_research = any(keyword in content_lower for keyword in HIGH_RISK_KEYWORDS)

if force_research:
    query = f"{market} advertising regulation: {content_to_analyze[:200]}"
    logger.info("[%s] High-risk content detected, forcing research: %s", step_name, query[:100])
else:
    # Existing LLM decision logic
    decision_prompt = ...
```

---

### 4. No Absolute Ban Override in Decision Router

**File:** `backend/jusads_compliance/decision_router.py`  
**Function:** `route_compliance_decision`

**Problem:**
A gambling ad can return `risk_level="Low"` and `risk_percentage=0` and be routed to `"pass"`. There's no absolute ban check before the scoring logic.

**Fix Needed:**
```python
# ADD THIS AT THE TOP OF route_compliance_decision(), before any routing logic:

ABSOLUTE_BANS = [
    "gambling", "casino", "lottery", "betting", "slot",
    "poker", "blackjack", "roulette", "online gambling",
    "alcohol targeting muslim", "alcohol to muslim audience",
    "tobacco to minor", "cigarette to children",
]

def _is_absolute_ban(high_risk_indicators: list[str]) -> bool:
    """Check if any violation involves an absolute ban."""
    combined = " ".join(high_risk_indicators).lower()
    return any(ban in combined for ban in ABSOLUTE_BANS)

# Then inside route_compliance_decision():
if _is_absolute_ban(high_risk_indicators):
    logger.warning(
        "[DecisionRouter] Absolute ban detected in violations — forcing critical_regen"
    )
    return "critical_regen"

# THEN continue with existing risk_level/risk_percentage logic
```

---

### 5. Image OCR Text Extracted Twice

**File:** `backend/jusads_compliance/compliance_pipeline.py`  
**Functions:** `legal_research_agent` and `main_brain_analysis`

**Problem:**
For image checks, `legal_research_agent` runs a prescan and saves to `result["_ocr_text"]`. But `main_brain_analysis` never reads it — it runs a fresh prescan. The OCR text extracted for research is wasted.

**Fix Needed in `main_brain_analysis` (image block):**
```python
elif media_type == "image":
    with open(input_path, "rb") as f:
        image_bytes = f.read()
    mime_type = mimetypes.guess_type(input_path)[0] or "image/jpeg"

    # Check if OCR was already done by legal_research_agent
    ocr_text = result.get("_ocr_text")
    if not ocr_text:
        # Pre-scan: describe the image content
        prescan = gemini.models.generate_content(
            model=_MODEL,
            contents=[genai_types.Content(role="user", parts=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                genai_types.Part.from_text(text=IMAGE_PRESCAN_PROMPT),
            ])],
        )
        ocr_text = prescan.text.strip()
        result["_ocr_text"] = ocr_text  # Cache it

    # Continue with compliance check using the cached OCR text
```

---

### 6. Hardcoded Rules in compliance_framework.md

**File:** `backend/shared/prompts/compliance_framework.md`

**Problem:**
The framework prompt contains hardcoded content rules like:

```markdown
### LANGUAGE COMPLIANCE (HARD RULE — Non-Negotiable)
Language mismatch is the ONLY absolute violation...

### PRODUCT CONTEXT RULES
- Skincare/Beauty: Showing product application on skin... is STANDARD — do not flag
```

These fixed rules can override genuine DB rules and cause the model to deprioritize gambling/legal bans.

**Fix Needed:**
Replace the entire content section with a dynamic evaluation scaffold:

```markdown
## EVALUATION FRAMEWORK

### GROUNDING REQUIREMENT (Critical)
You MUST base every violation solely on the regulatory rules provided in `{rules_text}`.
Do NOT invent rules. Do NOT use rules from your training data.
Do NOT cite frameworks, documents, or regulations not present in {rules_text}.

### ABSOLUTE BAN DETECTION
Before scoring, scan for categories which carry automatic 100% risk:
- Gambling, casino, lottery, betting promotions
- Alcohol advertising targeting Muslim demographics
- Tobacco targeting minors
- Any content explicitly prohibited by rules in {rules_text}

If present: set risk_percentage=100, risk_level="Critical", compliance_verdict="rejected".

### INCOMPLETE INPUT HANDLING
If media/text is empty or unreadable:
- Set evaluation_status="incomplete"
- Set risk_percentage=0
- Set compliance_verdict="incomplete_evaluation"
- Set explanation="No content was provided or detectable."

Do NOT treat empty input as passing.

### RESEARCH-AUGMENTED CONTEXT
{research_context}
Research context supplements {rules_text} but does not override it.

### BUSINESS CONTEXT
{business_context}

Use this to understand product category for context-aware evaluation.
```

---

## 🔴 REMAINING FRONTEND ISSUES

### 1. Metadata Tags Drop to Single "Market" Tag

**File:** `frontend/src/pages/compliance.tsx`  
**Function:** `handleSubmit` callback

**Problem:**
The backend doesn't always include `ethnicity`, `age_group`, and `platform` in the returned `result` object. They're stored separately in the `compliance_checks` table. The frontend displays tags based on `result.ethnicity`, etc., so they disappear.

**Fix Needed:**
After `complianceCheck.submit()` resolves, enrich the result with the upload params:

```typescript
const result: ComplianceResult = await complianceCheck.submit({...});

// Enrich result with metadata from upload params
result.ethnicity = result.ethnicity || params.ethnicity;
result.age_group = result.age_group || params.ageGroup;
result.platform = result.platform || params.platform;
result.market = result.market || params.market;

dispatch({ type: "SET_RESULT", projectId: id, result });
```

---

### 2. Image Container Vanishes for Text Checks

**File:** `frontend/src/components/compliance/ReviewStep.tsx`

**Problem:**
The image viewer block is gated on `hasAnyImage`, which is false for text checks. This causes the layout to collapse.

**Fix Needed:**
Don't conditionally hide the entire block — render a placeholder:

```tsx
{isImage && (
  <div className="result-card ...">
    {hasAnyImage ? (
      // existing tab viewer with Original/Segmented/Remix tabs
    ) : (
      <div className="p-8 flex items-center justify-center text-text-muted text-xs">
        Image not available for this media type
      </div>
    )}
  </div>
)}
```

---

### 3. "All Checks Passed" Shows for Empty Text

**File:** `frontend/src/components/compliance/ReviewStep.tsx`

**Problem:**
When text is empty, `hasViolations` is false, so it falls through to the "All checks passed" panel.

**Fix Needed:**
Check for incomplete evaluation state:

```tsx
const isIncomplete = !!(result as any).error || 
  (result as any).evaluation_status === "incomplete";

// Then in render:
{isIncomplete && (
  <div className="result-card ... border-amber-500">
    <p className="font-semibold text-amber-600">Incomplete Evaluation</p>
    <p className="text-xs text-text-muted">
      {(result as any).error ?? "No content was provided for evaluation."}
    </p>
  </div>
)}

{!hasViolations && !isIncomplete && (
  // existing "All checks passed" block
)}
```

---

### 4. Segmented Image URL Not Constructed Properly

**File:** `frontend/src/components/compliance/ReviewStep.tsx`

**Problem:**
`result.s3_segmented_key` is a raw S3 key, not a full URL. The frontend tries to use it directly as an image source and it fails.

**Fix Needed:**
Check if the backend exposes a `/api/compliance/asset?key=...` endpoint. If yes, construct the URL:

```tsx
const segmentedUrl = isImage && result.s3_segmented_key 
  ? `${API_BASE}/api/compliance/asset?key=${encodeURIComponent(result.s3_segmented_key)}`
  : null;

const originalUrl = isImage && result.s3_upload_key
  ? `${API_BASE}/api/compliance/asset?key=${encodeURIComponent(result.s3_upload_key)}`
  : null;
```

If that endpoint doesn't exist, the backend needs to add it to serve S3 objects via signed URLs.

---

## 📋 IMPLEMENTATION CHECKLIST

### Backend (Priority Order)

- [x] Fix persona lookup to fall back to `age_group='base'`
- [x] Remove double tracker calls in `routes/compliance.py`
- [ ] Wire `_research_context` into all compliance prompts
- [ ] Add absolute ban pre-check in `decision_router.py`
- [ ] Add high-risk keyword pre-check in `legal_research_agent`
- [ ] Fix empty text to return `evaluation_status="incomplete"`
- [ ] Remove hardcoded rules from `compliance_framework.md`
- [ ] Reuse OCR text from research agent in `main_brain_analysis`

### Frontend (Priority Order)

- [ ] Enrich result metadata after `checkCompliance` resolves
- [ ] Add incomplete state check before "All checks passed"
- [ ] Fix image URL construction for S3 keys
- [ ] Add placeholder for image viewer on non-image media types

### Prompt Templates

- [ ] Add `{research_context}` to `text_compliance.md`
- [ ] Add `{research_context}` to `image_compliance.md`
- [ ] Add `{research_context}` to `audio_compliance.md`
- [ ] Add `{research_context}` to `video_compliance.md`
- [ ] Add `evaluation_status` field to output schema in all prompts
- [ ] Replace `compliance_framework.md` with pure evaluation scaffold

---

## 🎯 ROOT CAUSE SUMMARY

The gambling ad passed because of a **perfect storm of 3 bugs**:

1. **Research agent decision was too lenient** → Gemini decided gambling didn't need research
2. **Research output was silently dropped** → Even when research ran, it never reached the main analysis
3. **No absolute ban check** → The decision router only looked at risk scores, not content type

Fixing all three ensures that:
- High-risk content (gambling, casino, alcohol) always triggers research
- Research results are injected into the compliance analysis prompt
- Absolute bans override any risk score and force rejection

---

## 📊 ESTIMATED IMPACT

| Fix | Impact | Effort |
|-----|--------|--------|
| Wire research context into prompts | **HIGH** — makes Tavily research actually useful | 15 min |
| Add absolute ban pre-check | **HIGH** — prevents gambling/casino from ever passing | 10 min |
| Fix empty text handling | **MEDIUM** — prevents false positives | 10 min |
| Remove hardcoded rules from framework | **HIGH** — lets DB rules take precedence | 20 min |
| Fix frontend metadata tags | **LOW** — cosmetic UI fix | 10 min |
| Fix persona lookup | **MEDIUM** — ensures persona data flows correctly | Already done ✅ |
| Fix double execution | **LOW** — reduces DB noise | Already done ✅ |

---

**Total remaining work:** ~1.5 hours backend + 30 min frontend = **2 hours to fix all issues**
