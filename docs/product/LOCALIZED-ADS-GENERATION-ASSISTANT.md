# Localized Ads Generation Assistant

Status: canonical product and agent operating brief  
Source: user-supplied brief, preserved in the repository on 2026-07-23

## Product outcome

Turn one approved campaign concept into persuasive, localized, platform-ready ad assets without inventing facts, mixing languages unintentionally, allowing captions/audio/on-screen text to disagree, presenting literal translation as native localization, reusing stale output, or taking publishing and paid-media actions without explicit human approval.

The primary user is a marketer, founder, operator, or agency team member.

## Supported video modes

1. `speaker_led`
   - A visible person or character speaks on screen.
   - Script-to-audio, subtitle, and lip-sync review are required.
2. `voiceover`
   - Narration plays over visuals without requiring an on-screen speaker.
   - Script-to-audio and subtitle review are required; face-sync acceptance is not.
3. `music_first`
   - No spoken script is required.
   - Music, motion, product visuals, text cards, captions, pacing, and CTA carry the ad.
   - Missing narration must never block this mode.

## Verified input contract

Required before paid generation:

- source campaign brief;
- approved offer and CTA;
- approved product or service facts;
- target locale and language;
- platform and aspect ratio;
- selected creative mode;
- brand rules;
- legal or compliance constraints;
- forbidden claims or themes;
- whether code-switching is allowed;
- whether a visible speaker is required;
- whether music-first output is allowed.

Optional inputs include references, persona, emotional tone, pacing, subtitle/voice/music preferences, existing assets or scripts, and approved winning hooks.

The system must not fill missing facts with plausible defaults. Uncertainty must remain visible.

## Tool routing

- Gemini Omni: video ideation, video generation, structural variation, and visual editing.
- ElevenLabs: voice, dubbing, pacing, emotional refinement, cleanup, and music.
- Gemini Flash Image / Nano Banana: low-cost image ideation, product scenes, storyboards, thumbnails, edits, and aspect-ratio variants.

Use the cheapest safe validation step first. Static concepts and storyboards should validate the direction before premium video generation.

## Resource policy

Default task envelope:

- RM500 equivalent total;
- at most 10 Omni runs;
- ElevenLabs only for shortlisted candidates;
- low-cost image exploration remains tracked;
- at most 3 deep-refinement candidates;
- at most 2 final exports per shortlisted candidate;
- 45-minute workflow target;
- preserve one correction pass;
- human approval before publishing, external upload, customer contact, or paid action.

Every generation, dub, merge, export, and retry consumes budget. Stop when improvement becomes marginal or safe completion no longer fits the remaining budget. Report usage, remaining budget, and the justification for premium steps.

## Non-negotiable guardrails

- Never invent product facts, pricing, offers, proof, legal terms, certifications, or performance claims.
- Never conceal uncertainty, failures, or incomplete review.
- Never label a draft approved without an approval event.
- Never auto-publish, auto-contact, or auto-spend.
- Never call localization native without passing the required review.
- Invalidate relevant outputs when locale, creative mode, claims, CTA, platform, aspect ratio, or other key inputs change.
- Preview, copy, export, approval, subtitles, and audio must reference the same current version.

## Production acceptance gate

Before expensive rendering:

- scene duration matches the requested duration;
- every spoken scene has a script in speaker-led and voiceover modes;
- music-first is not blocked by missing speech;
- every scene has reviewed on-screen text;
- localized CTA matches the approved CTA;
- language follows the selected locale and code-switching policy;
- product facts, offer, and claims have been confirmed;
- localization and cultural fit have been reviewed;
- estimated usage fits the remaining run budget;
- a human explicitly approves the current storyboard.

## Iteration loop

For each iteration:

1. Inspect the actual workflow and reproduce the issue.
2. Select one issue in priority order: safety/approval/budget, correctness/stale state/export, quality/UX, then polish.
3. Define observable acceptance criteria.
4. Make the smallest complete fix while preserving guardrails.
5. Test the real workflow across modes, locales, platforms, input failures, lifecycle states, and output surfaces.
6. Review localization, audio/video/image quality, technical behavior, accessibility, mobile, and errors.
7. Report issue, criteria, change, test matrix, result, budget, risks, and next action.

Stop and ask for human direction when requirements conflict, safety could weaken, a business decision is unresolved, native review is needed, budget is inadequate, permissions or rights are unclear, external dependencies are unavailable, or retries stop producing meaningful improvement.

