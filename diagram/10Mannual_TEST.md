# 10 — Manual Test: Full System Integration (Phase A–D + Layout Refactor)

This is a comprehensive test covering everything built in this session's second half:

- **Phase A**: All settings (age group, market, language, product, gender) flow to the AI
- **Phase B**: Generated ads persist on refresh; video plan persists on refresh
- **Phase C1**: Compliance judge receives product context (fixes "pizza" hallucination)
- **Phase D**: Zernio distribution backend (endpoint ready)
- **Layout**: Output Gallery moved to its own "Outputs" tab (no longer blocks chat)

---

## ⚠️ ONE-TIME SETUP

1. Stop the backend.
2. Clear cache:
   ```powershell
   Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName -notmatch '\.venv' } | Remove-Item -Recurse -Force
   ```
3. Run the migration (if not done already):
   ```sql
   -- In Supabase SQL Editor
   ALTER TABLE public.generated_ads
   ADD COLUMN IF NOT EXISTS compliance_status text,
   ADD COLUMN IF NOT EXISTS compliance_result jsonb,
   ADD COLUMN IF NOT EXISTS compliance_check_id text,
   ADD COLUMN IF NOT EXISTS distributed_at timestamptz,
   ADD COLUMN IF NOT EXISTS distribution_platform text,
   ADD COLUMN IF NOT EXISTS distribution_post_id text;
   ```
4. Add to `backend/.env` (if you have Zernio keys):
   ```env
   ZERNIO_API_KEY=sk_your_key
   ZERNIO_ACCOUNT_TIKTOK=acc_your_tiktok_id
   ZERNIO_ACCOUNT_INSTAGRAM=acc_your_instagram_id
   ```
5. Restart both servers:
   ```bash
   cd backend && .venv\Scripts\activate && uvicorn app:app --reload --port 8000
   cd frontend && npm run dev
   ```

---

## PART 1 — Layout: Outputs Tab (no longer blocks chat)

### Test 1.1: Three tabs exist in the right panel (Passed)

**What to do:** Open a generation task.

**Expected:**
- The right panel has **3 tabs**: `Agent Chatbot` | `Outputs` | `Inspector`
- Default tab: Agent Chatbot.
- Chat area has NO gallery/storyboard below the messages — just the input box.

**Pass if:** The chat is clean with no output gallery blocking it.

---

### Test 1.2: Outputs tab shows generated ads (Passed)

**What to do:**
1. In the Chatbot tab, type: `Generate a text caption for a bubble tea promo`
2. Wait for generation to complete.
3. Click the **Outputs** tab.

**Expected:**
- The generated text ad appears in the Outputs tab gallery with its compliance badge and publish button.
- The Outputs tab label shows a count: `Outputs (1)`.
- The chat tab is still clean — no gallery cluttering it.

**Pass if:** Results show in Outputs tab, not in chat.

---

### Test 1.3: Chat remains usable after generation (Passed)

**What to do:**
1. After Test 1.2, switch back to **Agent Chatbot** tab.
2. Type: `Now generate an image version too`
3. Send.

**Expected:**
- The chat streams normally without being blocked by previous outputs.
- After generation, switch to Outputs tab → both ads are there (text + image).

**Pass if:** You can keep chatting without the gallery in the way.

---

## PART 2 — Settings Flow (Phase A)

### Test 2.1: All settings fields exist (Passed)

**What to do:** Click the **gear** icon → Settings panel opens.

**Expected (Target Consumer tab):**
- Market: Malaysia / Singapore
- Target Ethnicity: All / Malay / Chinese / Indian
- Age Group: Gen Z / Millennial / Gen X / Baby Boomer / All Ages
- Voiceover Gender: Female / Male / Mixed
- Copy Language: Auto / Bahasa Melayu / English / Mandarin / Tamil

**Expected (Generation tab):**
- Target Platform: TikTok (selected by default) / Instagram / YouTube / Shopee
- Product / Brand Name: text input
- Product Category: dropdown (13 options)
- Compliance Check: toggle
- Video V2: toggle

**Pass if:** All fields are present and selectable.

---

### Test 2.2: Settings influence generation output (Passed)

**What to do:**
1. Settings → Target Ethnicity = **Chinese**, Age = **Gen Z**, Language = **Mandarin**, Product Name = `Bubble Tea XYZ`, Category = Food & Beverage.
2. Close settings.
3. Type: `Generate a text caption for our new drink`
4. Check the output in the Outputs tab.

**Expected:**
- The text copy is in **Mandarin** (or Manglish with Chinese audience tone).
- It references the product ("Bubble Tea XYZ" or similar).
- The tone is Gen Z appropriate (trendy, informal, snappy).

**Pass if:** The output reflects the settings you chose (not generic Malay/formal).

---

### Test 2.3: Different ethnicity = different output (Passed)

**What to do:**
1. Change ethnicity to **Malay**, language to **Bahasa Melayu**, age = **Baby Boomer**.
2. Same prompt: `Generate a text caption for our new drink`

**Expected:**
- Text is in **formal Bahasa Melayu**.
- Tone is respectful, family-oriented (Baby Boomer appropriate).
- No pork/alcohol references.

**Pass if:** Visibly different from the Chinese Gen Z output.

---

## PART 3 — Persist on Refresh (Phase B)

### Test 3.1: Generated ads survive page refresh  (Passed)

**What to do:**
1. Generate at least one ad (text is fastest).
2. Note it in the Outputs tab.
3. **Refresh the page** (F5 / Ctrl+R).
4. Open the same task → go to Outputs tab.

**Expected:**
- The generated ad(s) are **still there** — loaded from the database on mount.
- Compliance badges show correctly.

**Pass if:** Outputs survive refresh. This was the #1 recurring bug — now fixed.

---

### Test 3.2: Chat history survives refresh (Passed)

**What to do:**
1. After the refresh in Test 3.1, check the **Agent Chatbot** tab.

**Expected:**
- Your previous conversation (user messages + agent replies) is restored from history.

**Pass if:** Chat messages are still there after refresh.

---

### Test 3.3: Video plan survives refresh (if you have V2 configured)

**Feedback** Can use Imagen 4 first then only use gemini flash
INFO:httpx:HTTP Request: GET https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/platform_rules?select=platform%2Cmedia_type%2Caspect_ratio%2Cmax_duration_seconds%2Cadditional_rules&platform=eq.tiktok&media_type=eq.video&limit=1 "HTTP/2 200 OK"
INFO:jusads_generation.platform_rules:[PlatformRules] Resolved rule for (tiktok, video): aspect_ratio=9:16, max_dimension=1080, max_duration_seconds=180
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO:jusads_generation.agents.video_v2:[VideoAgentV2] Director planned 5 scene(s)
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 200 OK"
INFO:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 0 generated: C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_0_666e20.jpg
INFO:agent.s3_client:Uploaded C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_0_666e20.jpg → s3://jusads-439033634294-ap-southeast-1-an/generated_ads/b93f6c05-cc33-4b9b-a376-a441286e3650/280379e5-d2f6-4d22-8f38-771464078cb0/plans/71cb949a/keyframe_0.jpg
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 200 OK"
INFO:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 1 generated: C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_1_92e420.jpg
INFO:agent.s3_client:Uploaded C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_1_92e420.jpg → s3://jusads-439033634294-ap-southeast-1-an/generated_ads/b93f6c05-cc33-4b9b-a376-a441286e3650/280379e5-d2f6-4d22-8f38-771464078cb0/plans/71cb949a/keyframe_1.jpg
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 2 rate-limited (attempt 1/3); retrying in 8s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 2 rate-limited (attempt 2/3); retrying in 16s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 2 generation failed: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource has been exhausted (e.g. check quota).', 'status': 'RESOURCE_EXHAUSTED'}}
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Plan: scene 2 has no keyframe; omitting.
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 3 rate-limited (attempt 1/3); retrying in 8s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 3 rate-limited (attempt 2/3); retrying in 16s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 200 OK"
INFO:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 3 generated: C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_3_97e94f.jpg
INFO:agent.s3_client:Uploaded C:\Users\tanwa\AppData\Local\Temp\video_v2_plan_n641trwr\keyframe_3_97e94f.jpg → s3://jusads-439033634294-ap-southeast-1-an/generated_ads/b93f6c05-cc33-4b9b-a376-a441286e3650/280379e5-d2f6-4d22-8f38-771464078cb0/plans/71cb949a/keyframe_3.jpg
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 4 rate-limited (attempt 1/3); retrying in 8s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 4 rate-limited (attempt 2/3); retrying in 16s
INFO:google_genai.models:AFC is enabled with max remote calls: 10.
INFO:httpx:HTTP Request: POST https://aiplatform.googleapis.com/v1beta1/projects/project-d53d74fb-f547-4728-977/locations/global/publishers/google/models/gemini-3.1-flash-lite-image:generateContent "HTTP/1.1 429 Too Many Requests"
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Keyframe 4 generation failed: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource has been exhausted (e.g. check quota).', 'status': 'RESOURCE_EXHAUSTED'}}
WARNING:jusads_generation.agents.video_v2:[VideoAgentV2] Plan: scene 4 has no keyframe; omitting.
INFO:jusads_generation.agents.video_v2:[VideoAgentV2] Plan 71cb949a ready with 3 scene(s)     
INFO:httpx:HTTP Request: PATCH https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/tasks?id=eq.280379e5-d2f6-4d22-8f38-771464078cb0&project_id=eq.b93f6c05-cc33-4b9b-a376-a441286e3650 "HTTP/2 200 OK"
INFO:agent.supabase_client:Updated task 280379e5-d2f6-4d22-8f38-771464078cb0 -> status: in_progress
INFO:jusads_generation.orchestrator:[Orchestrator] Persisted video_plan on task 280379e5-d2f6-4d22-8f38-771464078cb0
INFO:httpx:HTTP Request: POST https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/chat_messages "HTTP/2 201 Created"
INFO:jusads_generation.chat_store:[ChatStore] Persisted assistant turn for task 280379e5-d2f6-4d22-8f38-771464078cb0 (message 14827e61-8778-415b-81a4-0a11a9e127fd)
INFO:jusads_generation.orchestrator:[Orchestrator] Generation run complete (0 ad(s) produced) 
INFO:httpx:HTTP Request: PATCH https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/tasks?id=eq.280379e5-d2f6-4d22-8f38-771464078cb0&project_id=eq.b93f6c05-cc33-4b9b-a376-a441286e3650 "HTTP/2 200 OK"
INFO:agent.supabase_client:Updated task 280379e5-d2f6-4d22-8f38-771464078cb0 -> status: completed


**What to do (requires Veo + image quota):**
1. Settings → Video V2 ON.
2. Generate a video: `Generate a TikTok video ad for a sports watch`
3. When the storyboard plan appears in the Outputs tab, **refresh the page**.
4. Reopen the task → Outputs tab.

**Expected:**
- The storyboard (scene cards + Continue button) is restored.
- You can still click Continue after the refresh.

**Pass if:** Video plan persists across refresh.

---

## PART 4 — Compliance Product Context (Phase C1)

### Test 4.1: Compliance judge knows the product (Passed)

**What to do:**
1. Settings → Product Name = `Iced Matcha Latte`, Category = Food & Beverage, Compliance ON.
2. Type: `Generate an image ad for our matcha drink`
3. Wait for compliance to run.
4. Check the Outputs tab → expand "Why this verdict".

**Expected:**
- The compliance result does **NOT** say "product mismatch" or "wrong product" or mention pizza.
- It evaluates the ad in the context of a matcha drink, not some random product.

**Pass if:** No "pizza vs matcha" hallucination — the judge knows it's a matcha ad.

---

## PART 5 — Distribution Endpoint (Phase D — backend only) (Passed)

### Test 5.1: Distribute endpoint exists (curl) 

**What to do:**
1. Publish an ad first (Test 1.2 → click Publish in Outputs tab).
2. Grab the `ad_id` from the Outputs tab or Supabase.
3. Hit the endpoint:
   ```bash
   curl -X POST "http://localhost:8000/api/projects/PROJECT_ID/tasks/TASK_ID/ads/AD_ID/distribute" -H "Content-Type: application/json" -d "{\"platform\": \"tiktok\", \"caption\": \"Check this out!\"}"
   ```

**Expected (if Zernio keys are NOT set):**
- `503 {"error": "ZERNIO_API_KEY is not configured..."}`

**Expected (if Zernio keys ARE set but account not connected):**
- `409 {"error": "No Zernio account configured for platform 'tiktok'..."}`

**Expected (if everything is set up and the account is real):**
- `200 {"post_id": "...", "status": "distributed", "platform": "tiktok"}`

**Pass if:** The endpoint responds correctly based on your config state.

---

### Test 5.2: Unpublished ad cannot be distributed (Passed) 

**What to do:**
1. Find an ad that is NOT published (status = completed, not published).
2. Hit the distribute endpoint for it.

**Expected:** `409 {"error": "Ad must be published before distributing"}`

**Pass if:** Distribution is gated behind publish.

---

## PART 6 — Platform Selector Fix

### Test 6.1: Platform selector renders correctly (Cannot test.)

**What to do:** Open Settings → Generation tab.

**Expected:**
- 4 platform buttons in a 2×2 grid: **TikTok** (selected by default), Instagram, YouTube, Shopee.
- No GSAP visibility glitch (buttons aren't invisible/cut off).
- Clicking a platform selects it with a clear active state.

**Pass if:** All 4 platforms are visible and selectable with no layout issues.

---

## Summary of what to look for

| # | Test | Key signal |
|---|------|-----------|
| 1.1 | Three tabs | No gallery in chat |
| 1.2 | Outputs tab | Ads show there with count badge |
| 1.3 | Chat usable | Can keep generating without being blocked |
| 2.1 | All settings | 10+ configurable fields across 2 tabs |
| 2.2 | Settings influence | Chinese Gen Z Mandarin output |
| 2.3 | Different = different | Malay Boomer Bahasa output |
| 3.1 | Persist ads | Still there after F5 |
| 3.2 | Persist chat | Messages restored |
| 3.3 | Persist plan | Storyboard + Continue after F5 |
| 4.1 | Product context | No "wrong product" hallucination |
| 5.1 | Distribute endpoint | Correct error/success based on config |
| 5.2 | Publish gate | 409 if not published |
| 6.1 | Platform selector | 4 visible buttons, no glitch |

---

## If something fails

- **Backend terminal**: look for `[Orchestrator]`, `[Distribution]`, `[ComplianceBridge]` log lines.
- **Frontend console (F12)**: check for React errors or failed API calls.
- **Stale cache**: if behavior doesn't match expectations, stop backend → clear `__pycache__` → restart.
- **Missing migration**: if distribution columns error, run migration 017 in Supabase SQL Editor.
