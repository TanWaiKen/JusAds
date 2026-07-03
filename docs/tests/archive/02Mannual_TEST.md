# 02 — Manual Test: Show Compliance Reasons ("Why this verdict")

**Enhancement:** Surface *why* an ad passed or failed compliance — not just the badge.
**What it does:** The compliance pipeline already produces a detailed analysis (risk level, explanation, flagged items, and a suggested fix). Until now that was computed and then thrown away — the UI only showed a green/red/amber badge. This change carries that analysis all the way to the output card as a collapsible **"Why this verdict"** panel.

---

## Before you start

Start both servers manually (in separate terminals):

```bash
# Backend
cd backend
.venv\Scripts\activate
uvicorn app:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

> ⚠️ **No database migration needed.** This feature reads the compliance analysis that the pipeline already computes at generation time and streams it to the UI. Nothing new is stored.

> ⚠️ **Clear the backend cache if `--reload` misses it:**
> `rmdir /s /q jusads_generation\__pycache__`

Open the app → open/create a project → open a **generation** task.

---

## What changed (so you know what you're looking at)

| Layer | File | Change |
|-------|------|--------|
| Backend | `backend/jusads_generation/compliance_bridge.py` | New `summarize_reasons()` — distills the big pipeline result into a compact `{risk_level, risk_percentage, explanation, suggestion, indicators}` payload |
| Backend | `backend/jusads_generation/state.py` | `GeneratedAdRef` gains a `compliance_reasons` field |
| Backend | `backend/jusads_generation/orchestrator.py` | Attaches `compliance_reasons` to each ad's SSE completed event and to the final `pipeline_state` |
| Frontend | `frontend/src/services/generationApi.ts` | New `ComplianceReasons` type + `normalizeComplianceReasons()` (snake_case → camelCase) |
| Frontend | `frontend/src/components/workspace/canvas/ChatbotPanel.tsx` | Carries `complianceReasons` through when mapping generated ads |
| Frontend | `frontend/src/components/workspace/canvas/OutputGallery.tsx` | New collapsible **"Why this verdict"** panel on each output card |

---

## Test 1: A non-compliant ad shows its reasons automatically (Works but not as good as we think)

**Feedback**
Generated ads show not compliacne, but funny tghings is that the result in the chat has make we can read the chat as it just show only and will not be found after refresh

**What to do:**
1. In **Settings**, make sure the compliance toggle is **ON**.
2. In the chat, generate an ad likely to fail — e.g. `Generate an image ad for a deodorant showing exposed armpits` (or reuse any ad you know comes back **Non-Compliant**).
3. Wait for the Output Gallery card to appear.

**Expected:**
- The card shows a red **Non-Compliant** badge.
- Directly below the caption there is a **"Why this verdict"** panel — and for non-compliant ads it is **already expanded**.
- Inside you should see some combination of:
  - A **risk level** next to the header (e.g. `· High (72%)`), colored red/amber.
  - An **explanation** paragraph.
  - A **Flagged items** list with red ✗ icons.
  - A **Suggested fix** line with a 💡 lightbulb.

**Pass if:** The non-compliant card explains *why* it failed, expanded by default.

---

## Test 2: The panel collapses and expands 

**What to do:**
1. On the same card, click the **"Why this verdict"** header.

**Expected:**
- The panel collapses; the chevron (▼) rotates.
- Click again → it expands back. Smooth, no layout jumps.

**Pass if:** Clicking the header toggles the details open/closed.

---

## Test 3: A compliant ad shows a reason panel too (collapsed) (Not ok)
**Feedback** The complainnt result just label only
![alt text](image-1.png)

**What to do:**
1. Generate an ad that should pass — e.g. `Generate a text caption for a family coffee shop promo in Bahasa Melayu`.

**Expected:**
- Green **Compliant** badge.
- A **"Why this verdict"** panel is present but **collapsed** by default.
- Expanding it shows the low risk level and the model's reasoning (explanation may be short).

**Pass if:** Compliant ads also carry an (collapsed) explanation you can open.

**Note:** If the compliant result had no explanation text at all, the panel may not appear — that's expected. It only shows when there's something meaningful to say.

---

## Test 4: Compliance turned OFF shows a "skipped" note (Passed)
**Feedback**
![alt text](image.png)

**What to do:**
1. In **Settings**, turn the compliance toggle **OFF**.
2. Generate any ad, e.g. `Generate a text caption for a sneaker sale`.

**Expected:**
- The badge shows **Pending** (amber) — because nothing was checked.
- If the "Why this verdict" panel appears, expanding it reads something like *"Compliance check was skipped: user disabled compliance check."*

**Pass if:** Skipping compliance is explained rather than shown as a silent amber badge.

---

## Test 5: Nothing breaks when there are no reasons (I cannot test)

**What to do:**
1. Generate a normal ad with compliance ON.

**Expected:**
- No crash, no empty gray box. If the backend returned no usable reason fields, the panel is simply absent and the card looks exactly like before (badge + publish button).

**Pass if:** Cards without reason data render cleanly, no empty panels.

---

## How to see the raw data (optional — for the curious)

Open the browser console (F12) → **Network** tab → find the `chat` request (it streams). Look at the streamed `data:` lines. On each media node's `completed` event and in the final `pipeline_state`, you'll now see a `compliance_reasons` object like:

```json
{
  "risk_level": "High",
  "risk_percentage": 72,
  "explanation": "72% risk due to exposed skin not suitable for the Malaysian market...",
  "suggestion": "Cover exposed areas, use modest wardrobe...",
  "indicators": ["exposed armpit", "revealing pose"]
}
```

That same object drives the panel.

---

## If something fails

Tell me which test number failed and what you saw. Common checks:
- **Backend terminal** — look for `[ComplianceBridge]` and `[Orchestrator]` log lines.
- **Browser console (F12)** — Network tab → the `chat` stream → confirm `compliance_reasons` is present in the events. If it's there but the panel isn't showing, it's a frontend mapping issue; if it's missing entirely, it's a backend issue.
- If you changed backend code and don't see an effect, clear `jusads_generation\__pycache__` and let uvicorn reload.
