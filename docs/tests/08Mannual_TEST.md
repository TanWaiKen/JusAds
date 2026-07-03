# 08 — Manual Test: Conditional Localization (if/else) + Hook-First Reels

Two refinements to Video V2 (and image ads):

1. **Conditional localization** — cultural rules now depend on the **target audience** instead of a blanket ban. Halal rules (no pork/alcohol, modest dress) apply **only** when the target is **Malay/Muslim**. Chinese and Indian audiences get their own rules (Indian avoids beef; Chinese allows pork/alcohol if relevant; etc.).
2. **Hook-first structure** — the first 1–2 scenes are now a scroll-stopping hook (can be playful/absurd, doesn't need to show the product), then product → benefit → call-to-action.

---

## ⚠️ ONE-TIME SETUP

1. Stop backend, clear cache:
   ```powershell
   Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName -notmatch '\.venv' } | Remove-Item -Recurse -Force
   ```
2. Restart backend + frontend.

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Backend | `jusads_generation/agents/video_v2.py` | Replaced blanket `_MALAYSIA_LOCALIZATION` with `_build_localization(ethnicity)` (per-audience rules) + `_normalize_ethnicity()`; director prompt is now hook-first; `plan_video`/`generate` accept `target_ethnicity` |
| Backend | `jusads_generation/orchestrator.py` | `run_generation(..., target_ethnicity)` threaded to `plan_video` |
| Backend | `routes/generation.py` | `ChatRequest.target_ethnicity` |
| Frontend | `services/generationApi.ts` | `TargetEthnicity` type; `sendChat`/`streamChat` accept it |
| Frontend | `components/workspace/canvas/GenerationCanvas.tsx` | New **Target Audience** selector in Settings (All / Malay / Chinese / Indian) with per-choice helper text |
| Frontend | `components/workspace/canvas/ChatbotPanel.tsx` | Passes `targetEthnicity` to `streamChat` |

---

## Test 1: The Target Audience selector exists

**What to do:**
1. Open **Settings** (gear).

**Expected:**
- Below the platform selector, a **Target Audience (Malaysia)** row with 4 buttons: **All / Malay / Chinese / Indian**.
- Selecting each shows a short helper line describing its cultural rules.
- Defaults to **All**.

**Pass if:** The selector is present and switches with helper text.

---

## Test 2: Malay audience → halal-friendly

**What to do:**
1. Set audience = **Malay**.
2. Generate an image ad: `Generate an image ad for a weekend food promo`

**Expected:**
- Malay Malaysian casting, modest dress, no pork/alcohol imagery, wholesome/family framing. Copy tends toward Bahasa Melayu.

**Pass if:** The output respects halal-friendly rules.

---

## Test 3: Chinese audience → different rules

**What to do:**
1. Set audience = **Chinese**.
2. Generate: `Generate an image ad for a weekend food promo`

**Expected:**
- Chinese Malaysian casting; pork/alcohol may appear if relevant to the product; may lean festive (CNY) themes. It is **not** forced into halal-only framing.

**Pass if:** The output is clearly tailored differently from the Malay run (the prohibitions are conditional, not blanket).

---

## Test 4: Indian audience → no beef, veg-friendly

**What to do:**
1. Set audience = **Indian**.
2. Generate: `Generate an image ad for a weekend food promo`

**Expected:**
- Indian Malaysian casting; no beef; vegetarian-friendly options welcome; may lean Deepavali themes.

**Pass if:** The output avoids beef and reflects Indian-Malaysian cultural cues.

---

## Test 5: Hook-first Video V2 storyboard

**What to do:**
1. Set audience to any value, turn **Video V2** ON.
2. Type: `Generate a TikTok video ad for a new kopi drink`
3. When the storyboard appears, read the first 1–2 scene cards.

**Expected:**
- The **first scene(s)** are a HOOK — attention-grabbing, possibly playful/absurd, and may **not** show the product yet. The hook subtitle is the most curiosity-driving line.
- Middle scenes show the product/benefit; the last is a call-to-action.

**Pass if:** The opening scenes are clearly a hook, not a plain product intro.

---

## Test 6: Hook + audience carry into the final video

**What to do:**
1. Click **Continue — Render Video** on the storyboard from Test 5.

**Expected:**
- The rendered video opens with the hook, flows to product → CTA, and its visuals/voiceover match the chosen audience's cultural rules.

**Pass if:** The final video is hook-first and audience-appropriate.

---

## Notes

- Audience defaults to **All** (inclusive: mixed cast, kept universally safe — avoids pork/beef/alcohol so it's safe for everyone at once). Pick a specific audience to unlock that community's specific allowances.
- The number of hook scenes is 1 for short storyboards (≤3 scenes) and 2 for longer ones.

---

## If something fails

Paste backend logs. The director prompt now includes the audience block and hook instructions; if outputs ignore them, it's a prompt-adherence issue we can tighten.
