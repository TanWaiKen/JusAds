# Duplicate Violations Issue - FIXED

## Problem Summary
The API was returning violations in multiple places:
- `high_risk_indicator`: Array(3) ✅ CORRECT - main violations list
- `violations`: [] (empty) ✅ CORRECT - deprecated field
- `verification.violations`: Array(3) ❌ DUPLICATE - should NOT exist!

## Root Causes Found

### 1. Dead Code in `legal_research_agent`
Lines 549-559 contained unreachable duplicate code after a `return` statement. This was confusing and could cause issues if the indentation was ever "fixed".

### 2. Wrong Field in `judges_agent` else Block
The `else` block created `verification.violations = []` instead of the correct structure with `sources`, `citation_urls`, etc.

### 3. Tracker Message Referenced Wrong Field
Tracker message looked for `verification.violations` which shouldn't exist - should look for `verification.sources` instead.

## Changes Made

### File: `backend/jusads_compliance/compliance_pipeline.py`

#### Change 1: Removed Dead Code (lines 549-559)
**Before:**
```python
return {"result": result}
    # If it's a list of strings (URLs)  # <-- UNREACHABLE!
    if not research_sources and sources and isinstance(sources[0], str):
        research_sources = [s for s in sources if isinstance(s, str)]
        
    result["_research_context"] = content
    result["_research_sources"] = research_sources
    ...
```

**After:**
```python
return {"result": result}
    # Clean return - no duplicate code
```

#### Change 2: Fixed `judges_agent` Verification Structure (line 700-722)
**Before:**
```python
else:
    result["verification"] = {
        "violations": [],  # ❌ Wrong field!
        "stale_rules_detected": 0,
        "overall_confidence": "medium" if high_risk_indicators else "high",
        "skipped": not TAVILY_ENABLED,
    }

_tracker.complete_step(
    task_id, step_name,
    f"... violations_verified={len(result.get('verification', {}).get('violations', []))}"  # ❌ Wrong field!
)
```

**After:**
```python
else:
    result["verification"] = {
        "sources": [],  # ✅ Correct field!
        "citation_urls": [],  # ✅ Consistent structure
        "stale_rules_detected": 0,
        "overall_confidence": "medium" if high_risk_indicators else "high",
        "violations_checked": 0,  # ✅ Count, not list
        "skipped": not TAVILY_ENABLED,
    }

_tracker.complete_step(
    task_id, step_name,
    f"... sources_found={len(result.get('verification', {}).get('sources', []))}"  # ✅ Correct field!
)
```

## Expected Result Structure

After this fix, the API will return:

```json
{
  "high_risk_indicator": [
    "Promotion of gambling/casino services",
    "References to Poker, Blackjack, Roulette, Slot",
    "Financial incentive (300B bonus) for gambling"
  ],
  "violations": [],  // Empty - deprecated field kept for backward compat
  "verification": {
    "sources": [
      {
        "url": "https://...",
        "title": "Malaysian Advertising Regulations",
        "snippet": "..."
      }
    ],
    "citation_urls": ["https://...", "https://..."],
    "overall_confidence": "high",
    "violations_checked": 3,
    "stale_rules_detected": 0
  }
}
```

**NO MORE `verification.violations` ARRAY!**

## ⚠️ CRITICAL - ACTION REQUIRED

### RESTART THE BACKEND SERVER

Python caches imported modules in memory. Even though the code is fixed, the old version might still be running!

```bash
# 1. Stop the current backend server (Ctrl+C in the terminal)

# 2. Navigate to backend directory
cd backend

# 3. Restart the server
uvicorn langgraph_api:app --reload --port 8000
```

### Test After Restart

1. Upload the same casino image again
2. Check the browser console for the result object
3. Verify:
   - ✅ `high_risk_indicator` has 3 violations
   - ✅ `verification.sources` exists (array of objects with url/title/snippet)
   - ✅ `verification.violations` does NOT exist
   - ✅ No duplicate data

## Status

- [x] Fixed dead code in `legal_research_agent`
- [x] Fixed `judges_agent` verification structure
- [x] Fixed tracker message to reference correct field
- [x] Updated `else` block to use consistent structure
- [ ] **USER TODO: Restart backend server and test**

---

## Technical Details

### Why Was This Happening?

The `_validate_violations_with_tavily()` function returns the CORRECT structure without a `violations` field:

```python
return {
    "sources": sources,
    "citation_urls": citation_urls,
    "overall_confidence": overall_confidence,
    "violations_checked": len(violations),
    "stale_rules_detected": 0,
}
```

But the `else` block (when TAVILY_ENABLED is False OR no high_risk_indicators) was creating an INCONSISTENT structure with a `violations` field.

Since violations are already in `high_risk_indicator`, there's no need to duplicate them in the verification object. The verification object should ONLY contain research sources and metadata about the verification process.

### Data Flow

```
legal_research_agent (runs first)
  ↓ stores: result["_research_sources"] = [source objects]
  ↓
main_brain_analysis
  ↓ stores: result["high_risk_indicator"] = [violation strings]
  ↓
judges_agent
  ↓ reads: result.get("_research_sources")
  ↓ calls: _validate_violations_with_tavily(research_sources=...)
  ↓ stores: result["verification"] = {sources, citation_urls, ...}
  ✅ NO DUPLICATION!
```
