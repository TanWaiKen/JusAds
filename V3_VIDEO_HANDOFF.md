# V3 Video Generation Handoff

## Current state

The V3 graph is working through planning and visual pre-production:

- Uploaded references are persisted and visible in a `References (N)` node.
- References feed the Character Sheet and Scene Grid generation stages.
- Character Sheet, Scene Grid, sliced frames, Director script, and `video_plan` are now persisted in `tasks.pipeline_state`.
- New Advanced tasks default to V3.
- V3 uses `gemini-3.1-flash-image` for reference-aware Character Sheet and Scene Grid creation.

Verified task: `253c71dc-c4b0-4d3c-84e8-c1f08c848ee9`.

## Critical blockers before “Continue to video”

### 1. V3 Omni uses the wrong API

`backend/jusads_generation/agents/video_v3_grid.py` calls Gemini Omni with
`gemini.models.generate_content(...)`.

Gemini Omni rejects this with:

```text
gemini-omni-flash-preview is only supported in the Interactions API
and cannot be called directly via generateContent.
```

Use Vertex Interactions API instead:

```text
POST https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/global/interactions
```

There is a working reference implementation in:

`backend/jusads_compliance/remediation_executor.py::_execute_omni_video_edit`

Reuse its Google ADC token, temporary GCS upload, interaction response parsing,
and output download pattern. Do not expose credentials to the client.

### 2. Omni does not currently receive the original product references

The V3 image stages receive the original uploaded assets. At production time,
Omni receives only the sliced Scene Grid frames and the combined scene prompt.

Pass all of the following to the Interactions API:

1. Original product/package reference(s).
2. Original brand/logo reference(s).
3. First, middle, and final Scene Grid frames.
4. The Director scene prompt and a final-CTA constraint.

Use the original product assets as high-priority references. The Scene Grid is a
continuity reference, not a replacement for the exact packaging reference.

### 3. Brand/product mismatch needs an approval gate

The test brief asked for **EverDry**, but the persisted Director plan used
**Nimbus** because one uploaded reference was named `nimbushealthco_logo.jpg`.

Do not infer the campaign brand from filenames alone. Before Stage 2 or before
production, reconcile the brief, product reference, and logo reference:

- Extract the requested brand from the user brief / structured product name.
- Identify visible logo text from the selected reference assets.
- If they conflict, pause with a clear choice: “Use EverDry” or “Use Nimbus”.
- Persist the approved brand in `video_plan.brand` and include it in every
  Character Sheet, Scene Grid, Omni, caption, and on-screen-copy prompt.

### 4. Product ending is not guaranteed

The current final scene only requests a subtle logo watermark. It does not
require the exact package to appear at the end.

When the user asks for a product reveal, append this production constraint:

```text
Final 1–2 seconds: show the exact supplied product package and approved brand
logo clearly but naturally. Preserve all visible package text and do not invent
claims, certifications, prices, or product features.
```

This should be opt-in from the storyboard/CTA settings, not implicit for every
video.

### 5. Requested 15 seconds currently plans approximately 12 seconds

`_SCENE_CLIP_SECONDS = 6` and a 15-second request currently yields two scenes,
so the production prompt asks for `6 * 2 = 12s`.

Fix one of these approaches:

- Use two 7.5-second clips when the model supports it; or
- Use three 5-second clips; or
- Make the UI honestly display the actual generated duration.

The persisted `duration_sec: 15.0` must match the generated output duration.

### 6. Interactions may be asynchronous

Do not assume the first Interactions API response already includes a video.
Handle `pending` / `processing` responses by polling the interaction until it is
completed, failed, or times out. Stream node-status SSE updates while polling.

## Recommended production design

```text
Original refs ─┐
               ├─ Character Sheet ─ Scene Grid ─ sliced frames ─┐
Brand approval ┤                                                  ├─ Omni Interactions API ─ video
Director plan ─┘                                                  │
Original product/logo refs ──────────────────────────────────────┘
```

Use the scene frames for person, wardrobe, shot continuity, and visual style.
Use original references for exact product/brand identity.

## Non-blocking follow-ups

- Add a Reference Inspector panel showing filename, role (product/logo/style),
  and the actual image at a larger size.
- Add a `final_product_reveal` storyboard toggle and expose it in Easy and
  Advanced mode.
- Add a preflight panel that lists: brand, product, language, duration,
  reference count, selected model, and expected output channels.
- For “generate everything needed”, create text/audio assets even when a target
  platform has no standalone text/audio rule, instead of rejecting them.
- Persist Omni interaction ID, input GCS URIs, output GCS URI, model, duration,
  and status in video metadata for retry/debugging.

## Validation checklist

1. Create a fresh Advanced task with three references: package, logo, style.
2. Confirm V3 is enabled by default.
3. Confirm `References (3)` displays thumbnail previews and connects to the
   Director, Character Sheet, and Scene Grid nodes.
4. Confirm Director plan uses the user-approved brand, exact requested language,
   and a duration matching the planned clips.
5. Confirm the final storyboard scene explicitly includes the requested product
   reveal when enabled.
6. Continue to production and verify SSE shows: upload refs → submit interaction
   → poll interaction → download output → assemble → persist result.
7. Confirm the output video preserves product packaging and brand identity, has
   no invented claims, and exposes the CapCut draft / final asset URLs.
