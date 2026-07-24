# Ads Generation Validation Loop

Use this loop for every production change to image, audio, or V3 video generation. A completed render is not proof that a campaign is accurate, localised, or safe to publish.

## Test matrix

| Case | Input | Required result | Reject when |
| --- | --- | --- | --- |
| Malay-localised food ad | Malay, Malaysia, explicit `ms`, verified certification evidence if any | Bahasa Melayu copy; culturally appropriate setting and attire; only supplied claims | The creative invents a halal/JAKIM badge or treats audience selection as certification |
| Malay-localised food ad without evidence | Same audience, no certificate supplied | Neutral product presentation; no halal wording or logo | A claim or badge is rendered |
| Chinese Malaysian campaign | Chinese, Malaysia, user-selected `zh` or `en` | The requested language is used; no stereotype-based visual assumption | Language or ethnicity is guessed from a generic market setting |
| Music-only V3 video | `music_only` | No spoken narration; a duration-matched Eleven Music track replaces native audio | Speech from Omni remains or music ends before the video |
| Video reference | Uploaded MP4 such as `assets/Uniqlo.mp4` | Three representative stills appear in the References node and guide the Scene Grid/Omni request | The MP4 is silently ignored or sent as an image MIME payload |

## Per-run gate

1. Record the brief, market, requested language, audience preference, supplied reference assets, and supplied certification evidence.
2. Review the Director plan before rendering: language, claim wording, character necessity, subtitle text, sound mode, and product reveal must be explicit.
3. Review the Scene Grid/reference frames. Reject identity drift, invented product features, invented certificates, or unsuitable context before any Omni run.
4. Render the 15-second V3 video (two Omni segments). Keep a maximum of ten Omni runs per campaign validation cycle; stop early if a systematic defect is found.
5. Inspect final media with `ffprobe`: expected duration, H.264 video, AAC audio when selected, no audio for `silent`, and 48 kHz stereo for an ElevenLabs program track.
6. Run a post-generation compliance review before publication. A successful generation result remains a creative draft, not an approval.

## Audio decisions

- `elevenlabs`: expressive ElevenLabs narration plus an instrumental Eleven Music bed; the final program replaces Omni audio.
- `music_only`: instrumental Eleven Music only; no scripted narration.
- `native_omni`: retain model-native ambience; use only after reviewing its language and content.
- `silent`: remove audio entirely for later licensed/creator editing.

ElevenLabs dubbing is not the default for new ads. Use dubbing only when localising an existing spoken source video and preserve a human review step for terminology, timing, and brand claims.

## Evidence rule

Localisation may use market rules and persona guidance. Certification claims require campaign-specific proof. The generator must not infer halal status, regulator approval, medical efficacy, or product safety from the target audience, product category, or reference imagery.
