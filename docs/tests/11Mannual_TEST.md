# 11 — Intelligent Remediation Engine: AI Tool Router (Phase R1)

**Date:** July 3, 2026  
**Feature:** AI-driven tool routing for compliance remediation  
**What it does:** Instead of always re-generating content, the AI analyzes violation severity and picks the cheapest/fastest tool that can fix it.

---

## Prerequisites

1. Backend running: `uvicorn app:app --reload --port 8000` (from `backend/`)
2. You have at least one compliance check that found violations (status = "checked", risk_level ≠ "Low")
3. Run migration: Execute `backend/migrations/018_brand_voices_table.sql` in your Supabase SQL editor

---

## Test 1: Routing Preview (no execution)

**What:** See what the AI would decide without running any tools.

1. Pick a `check_id` from a previous non-compliant check (look in Supabase `compliance_checks` table for one with `risk_percentage > 30`)
2. In your browser or Postman:
   ```
   GET http://localhost:8000/api/compliance/{check_id}/routing-preview
   ```
3. **Expected response:**
   ```json
   {
     "check_id": "abc12345",
     "media_type": "image",
     "routing": {
       "media_type": "image",
       "overall_severity": "minor",
       "tools": [
         {
           "tool": "inpaint_area",
           "severity": "minor",
           "reasoning": "...",
           "target_description": "...",
           "estimated_cost": "low",
           "estimated_time_seconds": 15
         }
       ],
       "strategy_summary": "...",
       "preserves_original": true,
       "confidence": 0.85
     }
   }
   ```
4. ✅ **Pass if:** Response has `routing.tools` array with at least 1 tool, severity is one of minor/moderate/major

---

## Test 2: Smart Remediation (SSE stream)

**What:** Run the full intelligent remediation with live progress.

1. Use the same `check_id` from Test 1
2. In Postman (or curl):
   ```bash
   curl -N http://localhost:8000/api/compliance/{check_id}/smart-remediate -X POST
   ```
3. **Expected SSE events (in order):**
   - `{"type": "status", "step": "routing", "message": "AI analyzing violations..."}`
   - `{"type": "routing_decision", "severity": "...", "tools": [...], ...}`
   - `{"type": "status", "step": "executing", "message": "Executing N tool(s)..."}`
   - `{"type": "result", "status": "remediated", "output_url": "https://...", ...}`

4. ✅ **Pass if:** 
   - You see all 4 event types in order
   - Final `result` event has `status` of "remediated" or "partially_remediated"
   - If `status` is "remediated", there's an `output_url` pointing to S3

---

## Test 3: Severity Routing Logic

**What:** Verify the AI picks the right tools for different severities.

### 3a: Minor issue (image, risk ≤ 40%)
- Find/create a check with `risk_percentage` around 30-40%
- Run routing preview → Should select `inpaint_area` (NOT `imagen_full_regen`)

### 3b: Major issue (any type, risk > 70%)
- Find/create a check with `risk_percentage` around 80-100%
- Run routing preview → Should select a major tool:
  - Image: `imagen_full_regen`
  - Video: `veo_regenerate`
  - Audio: `elevenlabs_new_vo`
  - Text: `gemini_new_copy`

### 3c: Moderate issue (50-70% risk)
- Run routing preview → Should select moderate tools (not minor, not major)

✅ **Pass if:** Each severity bracket routes to the correct tool tier

---

## Test 4: Voice Clone (Audio only)

**What:** Clone a brand voice from audio and verify it's stored.

1. You need a compliance check on an AUDIO file (media_type = "audio")
2. Run:
   ```bash
   curl -X POST http://localhost:8000/api/compliance/{check_id}/clone-voice
   ```
3. **Expected response:**
   ```json
   {
     "status": "cloned",
     "voice_id": "...",
     "name": "Brand Voice - {check_id}",
     "project_id": "..."
   }
   ```
4. Check Supabase `brand_voices` table — should have a new row with status "active"
5. ✅ **Pass if:** Voice cloned successfully, record exists in DB

---

## Test 5: Fallback Behavior (Gemini unavailable)

**What:** When Gemini is down, the router should fall back to heuristic (no crash).

1. Temporarily set an invalid API key in `.env` (e.g., `VERTEX_PROJECT_ID=invalid_xxx`)
2. Restart backend
3. Run routing preview for any check_id
4. **Expected:** Still returns a valid routing decision with `confidence: 0.5` (heuristic mode)
5. ✅ **Pass if:** No 500 error, routing still works with lower confidence

⚠️ **Remember to restore your valid API key after this test!**

---

## Test 6: Non-destructive (original preserved)

**What:** After remediation, the original file is still accessible.

1. Run smart-remediate on a check
2. After completion, verify:
   - `GET /api/media/{check_id}/original` → Still returns the original file
   - `GET /api/media/{check_id}/remixed` → Returns the new remediated file
3. ✅ **Pass if:** Both original AND remixed URLs work

---

## Quick Reference: New Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/compliance/{check_id}/smart-remediate` | Run AI-driven remediation (SSE) |
| GET | `/api/compliance/{check_id}/routing-preview` | Preview routing decision |
| POST | `/api/compliance/{check_id}/clone-voice` | Clone brand voice from audio |

---

## Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| 503 on all endpoints | Supabase unavailable | Check `.env` for SUPABASE_URL/KEY |
| Router always returns heuristic | Gemini init failed | Check VERTEX_PROJECT_ID in `.env` |
| Voice clone fails | ElevenLabs quota/key | Check ELEVENLABS_API_KEY, quota |
| "No source audio" on clone | Missing s3_upload_key | Re-upload audio via compliance check |
| Trim fails | FFmpeg not in PATH | Install FFmpeg, ensure `ffmpeg` is accessible |

---

## What's Next (Phase R2-R4)

- **R2:** Per-segment dubbing with timeline sync (replace just the bad 3 seconds)
- **R3:** Full CapCut API integration when official access is available
- **R4:** Frontend UI showing before/after comparison with tool badges
