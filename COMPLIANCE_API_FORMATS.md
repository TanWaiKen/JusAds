# JusAds Compliance API — Response Formats per Media Type

## Overview

The compliance API endpoint `POST /api/compliance/check` returns a streaming SSE response. The final event is `type: "result"` containing a `ComplianceResult` object. The shape of the `violations` array varies by media type.

## Common Response Envelope

All media types return this top-level structure:

```json
{
  "check_id": "chk_abc123",
  "media_type": "video" | "image" | "text" | "audio",
  "filename": "my_ad.mp4",
  "market": "malaysia",
  "ethnicity": "malay",
  "age_group": "25-34",
  "score": 63,
  "risk_level": "High" | "Medium" | "Low",
  "explanation": "Short reasoning about the compliance result...",
  "suggestion": "Concrete advice for fixing issues...",
  "localization": { ... },
  "persona": { ... } | null,
  "violations": [ ... ],
  "high_risk_indicators": ["indicator 1", "indicator 2"],
  "processing_time_seconds": 4.2
}
```

---

## Frontend Expectation (Current `Violation` Interface)

The frontend currently expects **every** violation to match this shape (designed for video):

```typescript
interface Violation {
  index: number;
  start: number;        // timestamp in seconds
  end: number;          // timestamp in seconds
  type: "visual" | "audio";
  category: string;
  severity: string;
  description: string;
  clip_url: string | null;
}
```

The frontend uses:
- `violation.category` → displayed as heading text
- `violation.severity` → badge color (error = red, warning = amber)
- `violation.type` → label next to severity
- `violation.description` → body text
- `violation.clip_url` → video player (shows "Clip unavailable" if null)
- `violation.start` / `violation.end` → formatted as `M:SS – M:SS` timestamps

**If any of these fields are missing, the UI breaks:**
- Missing `category` → shows "undefined"
- Missing `description` → shows "undefined"
- Missing `start`/`end` → shows "NaN:NaN – NaN:NaN"
- Missing `clip_url` (null) → shows "Clip unavailable" placeholder

---

## Video Violations ✅ (Works Correctly)

**Source:** `node_extract_clips()` in `langgraph_api.py` after the video compliance pipeline runs.

```json
{
  "index": 0,
  "start": 3.0,
  "end": 8.0,
  "type": "visual",
  "category": "Modesty",
  "severity": "error",
  "description": "Model wearing sleeveless top exposing shoulders",
  "clip_url": "/clips/chk_abc123_violation_0.mp4"
}
```

**Why it works:** All required frontend fields are present.

---

## Image Violations ❌ (Broken on Frontend)

**Source:** `high_risk_indicators` → converted in `langgraph_api.py`

**What the backend currently returns:**

```json
{
  "index": 0,
  "type": "visual",
  "component": "Exposed armpits on model",
  "severity": "error",
  "location_description": "",
  "edit_prompt": ""
}
```

**Why it's broken:** Missing `category`, `description`, `start`, `end`, `clip_url`. The frontend shows:
- "undefined" where `category` should be
- "undefined" where `description` should be  
- "Clip unavailable" (because no `clip_url`)
- "NaN:NaN – NaN:NaN" (because no `start`/`end`)

**Fix needed — the backend should return:**

```json
{
  "index": 0,
  "start": 0,
  "end": 0,
  "type": "visual",
  "category": "Visual Compliance",
  "severity": "error",
  "description": "Exposed armpits on model",
  "clip_url": null
}
```

OR the frontend needs to handle optional fields. The simplest backend fix is to map `component` → `description` and `category`, and add `start: 0`, `end: 0`, `clip_url: null`.

---

## Text Violations ❌ (Broken on Frontend)

**Source:** `high_risk_indicators` → converted in `langgraph_api.py`

**What the backend currently returns:**

```json
{
  "index": 0,
  "type": "text",
  "phrase": "4 out of 5 gynecologists",
  "severity": "error",
  "reason": "",
  "suggested_replacement": ""
}
```

**Why it's broken:** Missing `category`, `description`, `start`, `end`, `clip_url`.

**Fix needed — the backend should return:**

```json
{
  "index": 0,
  "start": 0,
  "end": 0,
  "type": "text",
  "category": "Text Compliance",
  "severity": "error",
  "description": "4 out of 5 gynecologists",
  "clip_url": null
}
```

---

## Audio Violations ❌ (Broken on Frontend)

**Source:** `high_risk_indicators` → converted in `langgraph_api.py`

**What the backend currently returns:**

```json
{
  "index": 0,
  "type": "audio",
  "spoken_phrase": "from your pits to your private areas",
  "severity": "error",
  "reason": "",
  "suggested_replacement": "",
  "voice_gender": ""
}
```

**Why it's broken:** Missing `category`, `description`, `start`, `end`, `clip_url`.

**Fix needed — the backend should return:**

```json
{
  "index": 0,
  "start": 0,
  "end": 0,
  "type": "audio",
  "category": "Audio Compliance",
  "severity": "error",
  "description": "from your pits to your private areas",
  "clip_url": null
}
```

---

## Summary: What Each Media Type is Missing

| Field | Video | Image | Text | Audio |
|-------|-------|-------|------|-------|
| `index` | ✅ | ✅ | ✅ | ✅ |
| `start` | ✅ | ❌ missing | ❌ missing | ❌ missing |
| `end` | ✅ | ❌ missing | ❌ missing | ❌ missing |
| `type` | ✅ | ✅ "visual" | ✅ "text" (but frontend expects "visual"\|"audio") | ✅ "audio" |
| `category` | ✅ | ❌ missing (has `component`) | ❌ missing (has `phrase`) | ❌ missing (has `spoken_phrase`) |
| `severity` | ✅ | ✅ | ✅ | ✅ |
| `description` | ✅ | ❌ missing (info is in `component`) | ❌ missing (info is in `phrase`) | ❌ missing (info is in `spoken_phrase`) |
| `clip_url` | ✅ | ❌ missing | ❌ missing | ❌ missing |

---

## Recommended Fix (Backend Only — Don't Touch Frontend)

In `backend/langgraph_api.py`, change the `high_risk_indicators` → violations conversion to always include the fields the frontend expects:

### Image Fix:
```python
response["violations"] = [
    {
        "index": i,
        "start": 0,
        "end": 0,
        "type": "visual",
        "category": "Visual Compliance",
        "severity": "error" if response.get("risk_level") == "High" else "warning",
        "description": indicator,
        "clip_url": None,
        # Keep remix-pipeline fields too
        "component": indicator,
        "location_description": "",
        "edit_prompt": "",
    }
    for i, indicator in enumerate(response["high_risk_indicators"])
]
```

### Text Fix:
```python
response["violations"] = [
    {
        "index": i,
        "start": 0,
        "end": 0,
        "type": "visual",  # frontend only supports "visual" | "audio"
        "category": "Text Compliance",
        "severity": "error" if response.get("risk_level") == "High" else "warning",
        "description": indicator,
        "clip_url": None,
        # Keep remix-pipeline fields too
        "phrase": indicator,
        "reason": "",
        "suggested_replacement": "",
    }
    for i, indicator in enumerate(response["high_risk_indicators"])
]
```

### Audio Fix:
```python
response["violations"] = [
    {
        "index": i,
        "start": 0,
        "end": 0,
        "type": "audio",
        "category": "Audio Compliance",
        "severity": "error" if response.get("risk_level") == "High" else "warning",
        "description": indicator,
        "clip_url": None,
        # Keep remix-pipeline fields too
        "spoken_phrase": indicator,
        "reason": "",
        "suggested_replacement": "",
        "voice_gender": "",
    }
    for i, indicator in enumerate(response["high_risk_indicators"])
]
```

---

## Alternative Fix (Frontend Only — If You Prefer)

Update the frontend `Violation` interface and components to handle optional fields:

1. Make `start`, `end`, `clip_url` optional in the `Violation` interface
2. In `ViolationClipPlayer`: don't render if `clip_url` is undefined AND `start`/`end` are undefined
3. In `ViolationCard`: fallback `category` to `component || phrase || spoken_phrase || type`
4. In `ViolationCard`: fallback `description` to `component || phrase || spoken_phrase || ""`

---

## File Locations

| What | Path |
|------|------|
| Backend API (violation conversion) | `backend/langgraph_api.py` lines ~370-410 |
| Frontend Violation type | `frontend/src/services/complianceApi.ts` line 9 |
| Frontend violation card | `frontend/src/components/compliance/DetailPanel.tsx` — `ViolationCard` |
| Frontend clip player | `frontend/src/components/compliance/ViolationClipPlayer.tsx` |
| Frontend compliance page | `frontend/src/pages/compliance.tsx` |
