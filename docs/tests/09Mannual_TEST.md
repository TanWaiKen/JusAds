# 09 — Manual Test: Tabbed Settings Panel (Target Consumer + Generation)

**Enhancement:** The old flat settings popup is replaced with a proper **two-tab Settings panel** (Vercel-style), with all the fields the AI uses to customize generation and compliance.

---

## Before you start

Restart both servers (backend + frontend). No migration needed.

---

## What changed

| Layer | File | Change |
|-------|------|--------|
| Frontend | `components/workspace/canvas/SettingsPanel.tsx` | **New** two-tab panel: Target Consumer + Generation, Vercel-inspired design (shadow-as-border, #171717 active states, clean typography) |
| Frontend | `components/workspace/canvas/GenerationCanvas.tsx` | Replaced old inline `SettingsPopup` with unified `GenerationSettings` state + `SettingsPanel` component |

### Tab 1 — Target Consumer (who the ad is reaching)

| Field | Options | What it affects |
|-------|---------|-----------------|
| **Market** | 🇲🇾 Malaysia / 🇸🇬 Singapore | Which regulatory regime + setting |
| **Target Ethnicity** | All (Mixed) / Malay / Chinese / Indian | Conditional cultural rules (halal, no-beef, etc.) + casting |
| **Age Group** | Gen Z (18-27) / Millennial (28-43) / Gen X (44-59) / Baby Boomer (60+) / All Ages | Tone, formality, slang level, compliance language rules |
| **Voiceover Gender** | Female / Male / Mixed | Which ElevenLabs voice is selected |
| **Copy Language** | Auto / Bahasa Melayu / English / Mandarin / Tamil | Language of subtitles, copy, voiceover script |

### Tab 2 — Generation (how the ad is made)

| Field | Options | What it affects |
|-------|---------|-----------------|
| **Target Platform** | TikTok / Instagram / Shopee | Aspect ratio, sizing, duration rules |
| **Product / Brand Name** | Free text | Context for the AI when generating |
| **Product Category** | Dropdown (Food, Fashion, Beauty, Tech, Health, Finance, Travel, Education, Real Estate, Automotive, Entertainment, E-Commerce, Other) | Helps compliance + generation be category-aware |
| **Compliance Check** | Toggle | Whether generated ads run through the compliance pipeline |
| **Video V2 — Multi-Scene** | Toggle | Storyboard planning flow vs. single Veo clip |

---

## Test 1: Settings opens with two tabs

**What to do:**
1. Click the **gear** icon in the canvas toolbar.

**Expected:**
- A centered overlay panel appears (Vercel-style: white card, shadow-as-border, clean tabs).
- Two tabs: **"Target Consumer"** and **"Generation"**.
- Default tab: Target Consumer.

**Pass if:** The tabbed panel appears with both tabs visible.

---

## Test 2: Target Consumer tab has all fields

**What to do:**
1. On the Target Consumer tab, scan all fields.

**Expected:**
- **Market**: Malaysia (default) / Singapore buttons.
- **Target Ethnicity**: All / Malay / Chinese / Indian — with a helper description underneath that changes per selection.
- **Age Group**: Gen Z / Millennial / Gen X / Baby Boomer / All Ages — with generation-style helper text (e.g. "Trendy, informal, snappy" for Gen Z).
- **Voiceover Gender**: Female (default) / Male / Mixed.
- **Copy Language**: Auto (default) / Bahasa Melayu / English / Mandarin / Tamil.

**Pass if:** All 5 fields are present, selectable, and descriptions update on selection.

---

## Test 3: Generation tab has platform + product + toggles

**What to do:**
1. Click the **"Generation"** tab.

**Expected:**
- **Target Platform**: TikTok / Instagram / Shopee selector (same as before).
- **Product / Brand Name**: Free text input with placeholder.
- **Product Category**: Dropdown with 13 categories.
- **Compliance Check**: Toggle (on by default).
- **Video V2**: Toggle (off by default).

**Pass if:** All fields are present and functional.

---

## Test 4: Settings persist within the session

**What to do:**
1. Set ethnicity = Chinese, age = Gen Z, platform = TikTok, product name = "Kopi Gao", category = Food & Beverage.
2. Close settings, then reopen.

**Expected:**
- All your selections are still there (state persists in React, not lost on close/reopen within the same session).

**Pass if:** Values are remembered across close/reopen.

---

## Test 5: Clicking outside closes the panel

**What to do:**
1. Open settings, then click the dark backdrop area outside the white card.

**Expected:**
- Panel closes smoothly.

**Pass if:** Clicking backdrop dismisses the panel.

---

## Known limitation

Settings are React state only — they don't persist to the DB yet. Refreshing the page resets them to defaults. This is a follow-up (persist settings per-project in Supabase).

---

## If something fails

Check browser console for errors. The panel is purely frontend — no backend changes this round.
