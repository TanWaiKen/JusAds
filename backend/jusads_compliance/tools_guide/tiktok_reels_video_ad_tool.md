# TikTok and Reels Video Ad Guide

## Introduction
Short-form video ads (9:16 aspect ratio, 15-30 seconds) on platforms like TikTok and
Reels require rapid hook-and-payoff pacing. They outperform other formats when styled
like native, User-Generated Content (UGC).

## 5-Part Short-Form Structure
1. **Hook (0-3s)**: Visually/audibly arresting. Bold overlay text (e.g. "Stop scrolling if you struggle with...").
2. **Problem (3-7s)**: Relatable pain point presentation.
3. **Solution/Product (7-12s)**: Satisfying reveal of the product.
4. **Proof/Demo (12-20s)**: Product in use or customer review.
5. **CTA (20-30s)**: Direct instruction (e.g. "Link in bio", "Shop 20% off").

## How the Video Agent Works
The Video Agent is a composer, not just a stitcher. It assembles a final video from:

1. **Visual** — an ad image from the Image Agent (or generated on demand).
2. **Voiceover** — produced by the Audio Agent, which plans its own script.
3. **Its OWN sound design** — the Video Agent independently generates a cinematic
   background sound/music bed via the ElevenLabs Sound Generation API, then mixes it
   (lowered volume) under the voiceover. This is separate from the audio ad's SFX.
4. **Assembly** — FFmpeg combines the still image and the mixed audio track into MP4.

## Audio & Dubbing
- Voiceover uses ElevenLabs TTS `eleven_multilingual_v2` with a market-matched voice.
- The Video Agent adds its own SFX bed for atmosphere — the video is NOT just a raw
  merge of the audio ad output.
- Ensure subtitles/text overlays are present since over 70% of viewers watch without sound.

## Output
- Upload MP4 to `generated_ads/{project_id}/{task_id}/video_{id}.mp4`.
- Record in `public.generated_ads` with `media_type='video'`.
