# Audio Ad Generation Guide

## Introduction
The Audio Agent is an autonomous specialist that **plans and produces a complete audio
advertisement** from a product brief. It does not simply read out the text caption —
it thinks about the product's value proposition, writes a persuasive multi-scene script,
and produces a fully mixed voiceover-plus-sound-effects track.

## Workflow (agentic, step by step)
The Audio Agent follows the proven 4-step audio_ads pipeline:

1. **Plan the script** (Gemini)
   - Analyze the product/campaign brief and target audience.
   - Identify the hook (scene 1) and the call-to-action (final scene).
   - Break the ad into 2-3 short scenes. Each scene has:
     - `script`: the spoken voiceover line (natural, persuasive)
     - `sfxPrompt`: a matching background sound effect description
     - `duration`: rough length in seconds

2. **Generate sound effects** (ElevenLabs Sound Generation API)
   - For each scene, generate an ambient SFX bed from `sfxPrompt`.

3. **Generate voiceover** (ElevenLabs TTS, `eleven_multilingual_v2`)
   - Synthesize each scene's `script` using a market-matched voice.
   - Voice is selected from `config.VOICE_CONFIG` by (market, ethnicity, gender).
   - Language code is enforced (e.g. `ms` for Malay, `en` for English).

4. **Mix and assemble** (pydub)
   - Overlay each scene's SFX (lowered ~10 dB) under its voiceover.
   - Concatenate all scenes into one final MP3.

## Voice Selection
- Malaysia Malay → Bahasa Malaysia voice
- Malaysia Chinese → Mandarin voice
- Singapore → English (Singaporean) voice
- Falls back to `config.DEFAULT_VOICE` when no exact match exists.

## Output
- Upload final MP3 to `generated_ads/{project_id}/{task_id}/audio_{id}.mp3`.
- Record in `public.generated_ads` with `media_type='audio'`, storing the full
  script text in `caption` and the scene breakdown in `metadata.scenes`.

## Key Principle
The Audio Agent owns the creative decision of **what to say** — it is a planner,
not a passive text-to-speech converter.
