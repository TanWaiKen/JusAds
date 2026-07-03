# 01 — Manual Test: Publish Gate (Human-in-the-Loop Approval)

**Enhancement:** Task 7 — Publish Gate (NIMBUS diagram § 4)
**What it does:** After an ad is generated, nothing is auto-distributed. The project owner reviews the output and clicks **Publish** to approve it. Ads that failed compliance are blocked from publishing.

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

> ⚠️ **Database note:** This feature uses the `published` value on the `generated_ads.status` column. That value already exists in migration `016_agentic_ad_studio_supabase.sql`, so **no new migration is needed**. If your Supabase DB was built from that file (or later), you're good.

Open the app → open/create a project → open a **generation** task.

---

## What changed (so you know what you're looking at)

| Layer | File | Change |
|-------|------|--------|
| Backend | `backend/jusads_generation/publish.py` | New `publish_ad()` — flips status to `published`, blocks non-compliant ads |
| Backend | `backend/routes/generation.py` | New endpoint `POST /api/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/publish` |
| Frontend | `frontend/src/services/generationApi.ts` | New `publishAd()` function + `PublishResult` type |
| Frontend | `frontend/src/components/workspace/canvas/OutputGallery.tsx` | New **Publish** button on each output card |

---

## Test 1: Publish button appears on a generated ad (Passed)

**Feedback**
We can use  Zernio in the future to make it possible
You use the same unified `/posts` endpoint for both TikTok and Instagram in Zernio; you just change the `platform` field (and optional platform‑specific settings). [zernio](https://zernio.com/tiktok-api)

Below are minimal examples you can drop into a backend or an agent.

***

## Base URL and auth

- Base URL: `https://zernio.com/api/v1` [zernio](https://zernio.com/tiktok-api)
- Auth: `Authorization: Bearer YOUR_API_KEY` (`sk_...` from Zernio dashboard) [zernio](https://zernio.com/tiktok-api)

***

## TikTok posting endpoint and code

Core endpoint (HTTP): [zernio](https://zernio.com/tiktok-api)

- Create/schedule TikTok post:  
  `POST https://zernio.com/api/v1/posts`  
  Body must include a `platforms` entry with `platform: "tiktok"` and the connected `accountId`. [zernio](https://zernio.com/tiktok-api)

Node.js example (from TikTok docs, shortened):

```js
const response = await fetch('https://zernio.com/api/v1/posts', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    content: 'How to build a social media app in 2026 #coding #developer #api',
    mediaItems: [
      { type: 'video', url: 'https://example.com/tutorial.mp4' }
    ],
    platforms: [{
      platform: 'tiktok',
      accountId: 'acc_abc123',                 // your TikTok account ID
      platformSpecificData: {
        tiktokSettings: {
          privacy_level: 'PUBLIC_TO_EVERYONE', // or followers/friends/private
          allow_comment: true,
          allow_duet: true,
          allow_stitch: true
        }
      }
    }],
    scheduledFor: '2026-03-15T14:00:00Z',      // or omit & use publishNow
    timezone: 'America/New_York'
  })
});

const post = await response.json();
console.log(post.post._id);
```

Key TikTok endpoints (all under `/api/v1`): [zernio](https://zernio.com/tiktok-api)

- `POST /posts` – create/schedule/draft TikTok posts  
- `GET /posts/{id}` – get status/details/metadata  
- `PUT /posts/{id}` – update scheduled post  
- `DELETE /posts/{id}` – cancel scheduled/delete draft  
- `GET /profiles` – list profiles (incl. TikTok accounts)  
- `GET /analytics/{postId}` – views, likes, comments, shares, engagement rate  

***

## Instagram posting endpoint and code

For Instagram feed posts/Reels/Stories, you still use `POST /posts` with `platform: "instagram"`. [zernio](https://zernio.com/instagram)

Basic JSON shape (from Instagram page):

```json
{
  "platforms": ["instagram"],
  "accountId": "acc_abc123",
  "content": "Hello from Zernio!",
  "scheduledFor": "2025-01-15T19:00:00Z"
}
```

Full JS example using the unified endpoint: [zernio](https://zernio.com/instagram)

```js
const response = await fetch('https://zernio.com/api/v1/posts', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    platforms: [{
      platform: 'instagram',
      accountId: 'your-instagram-account-id'
    }],
    content: 'Beautiful sunset at the beach! 🌅 #sunset #photography',
    mediaItems: [
      {
        type: 'image',
        url: 'https://your-image-url.jpg'
      }
    ],
    scheduledFor: '2024-01-15T19:00:00Z'
  })
});

const result = await response.json();
console.log('Scheduled successfully:', result.id);
```

Notes: [zernio](https://zernio.com/instagram)

- Reels: send short‑form video; Zernio publishes as a Reel (no separate Reels endpoint).  
- Stories: set the content type to “story” via platform settings (see platform‑settings docs), but still go through `POST /posts`.  

***

## Extra: Instagram tools (hashtag checker)

If you meant “API endpoint related to Instagram” more broadly, there is also an Instagram tools endpoint: [zernio](https://zernio.com/social-media-tools-api)

```bash
curl -X POST "https://zernio.com/api/v1/tools/instagram/hashtag-checker" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hashtags": ["travel", "followforfollow", "photography"]}'
```

***

Do you plan to call Zernio directly from your backend (Node/Python) or from an LLM agent/tooling layer (e.g., MCP/n8n), so I can shape the code samples around that stack?  

**What to do:**
1. In the chat, type: `Generate a text caption for a coffee shop promo`
2. Hit send and wait for the Output Gallery to appear below the chat.

**Expected:**
- The output card shows the media + a compliance badge (compliant / non-compliant / pending)
- Below that, a blue **Publish** button with a rocket icon 🚀

**Pass if:** The Publish button is visible on the generated ad card.

---

## Test 2: Publishing an ad works (Passed)

**Feedback**
INFO:httpx:HTTP Request: PATCH https://vxzzsqobqdotcsiseken.supabase.co/rest/v1/generated_ads?id=eq.1b9806dc-1297-4dcf-bd0c-789c8c7818d5 "HTTP/2 200 OK"
INFO:jusads_generation.publish:[Publish] Ad 1b9806dc-1297-4dcf-bd0c-789c8c7818d5 approved and published by owner
INFO:     127.0.0.1:55799 - "POST /api/projects/a8252e1a-e4f2-4184-92aa-28331341c749/tasks/414c8323-d8bc-496e-9bd1-f2a7b0532340/ads/1b9806dc-1297-4dcf-bd0c-789c8c7818d5/publish HTTP/1.1" 200 OK
In frontend it show published

**What to do:**
1. On a generated ad card, click **Publish**.

**Expected:**
- Button changes to **"Publishing..."** with a spinner
- After a moment it becomes a green **"Published"** ✅ badge (the button disappears)

**Pass if:** The card ends in the green "Published" state without errors.

**Verify in the database (optional):**
- Open Supabase → `generated_ads` table → find your row → `status` column should now read `published`.

---

## Test 3: Publishing is idempotent (no double-publish issues) (Dont Know)

**Feedback**
I cant even test this, becasue this is the know limiation as the geenrated content (Published button and the judges result not able to show again if we refresh if we can click the text agent geenrated result then decide whether can push or not will be better)

**What to do:**
1. Publish an ad (Test 2).
2. Reload the task / reopen the gallery, then look at the same ad.

**Expected:**
- No error. (Behind the scenes, re-publishing an already-published ad just returns success — it won't break.)

**Pass if:** No crash or error when the ad is already published.

> Note: right now the gallery does not yet *remember* the published state across a full page reload — it re-renders from the generation result. That's a known limitation (see "Known limitations" below). The important part is the backend does not error.

---

## Test 4: Compliance gate blocks non-compliant ads (Passed)


**What to do:**
1. Make sure the compliance toggle is **ON** in Settings (so compliance actually runs).
2. Generate an ad that is likely to fail compliance, or use one you know came back **Non-Compliant** (red badge).

**Expected:**
- Instead of a Publish button, the card shows a red notice:
  **"Blocked — resolve compliance to publish"** ⚠️
- There is no way to publish it from the UI.

**Pass if:** Non-compliant ads show the blocked notice and cannot be published.

---

## Test 5: Backend directly (optional — for the curious) (I think is passed)

**Feedback**
C:\Users\tanwa\OneDrive\TWK developer\Documents\Langhub-main>curl -X POST "http://localhost:8000/api/projects/a8252e1a-e4f2-4184-92aa-28331341c749/tasks/414c8323-d8bc-496e-9bd1-f2a7b0532340/ads/1b9806dc-1297-4dcf-bd0c-789c8c7818d5/publish
{"ad_id":"1b9806dc-1297-4dcf-bd0c-789c8c7818d5","status":"published","compliance_status":"non-final","already_published":true}
C:\Users\tanwa\OneDrive\TWK developer\Documents\Langhub-main>

If you want to hit the endpoint yourself, grab a `project_id`, `task_id`, and an `ad_id` (from the Supabase `generated_ads` table), then:

```bash
curl -X POST "http://localhost:8000/api/projects/PROJECT_ID/tasks/TASK_ID/ads/AD_ID/publish"
```

**Expected responses:**
| Situation | HTTP status | Body |
|-----------|-------------|------|
| Success | `200` | `{"ad_id": "...", "status": "published", "compliance_status": "...", "already_published": false}` |
| Ad doesn't exist | `404` | `{"error": "Generated ad ... not found ..."}` |
| Ad failed compliance | `409` | `{"error": "Ad failed compliance review and cannot be published"}` |
| DB unavailable | `503` | `{"error": "persistence store unavailable: ..."}` |

---

## Known limitations (intentional — not bugs)

1. **No real distribution yet.** Publishing only records approval (`status = published`) in the database. It does **not** push to TikTok / YouTube / Shopee APIs. That's a separate future step.
2. **Published state not persisted in the UI across reload.** The gallery shows "Published" right after you click, but a full page reload re-renders from the generation result and the button may reappear. The backend status is still correct. We can wire the UI to read the real status later if you want.

---

## If something fails

Tell me which test number failed and what you saw (a screenshot helps). Common things to check:
- Backend terminal — look for `[Publish]` log lines to see what happened.
- Browser console (F12) — network tab, find the `/publish` request and check its status code + response.
