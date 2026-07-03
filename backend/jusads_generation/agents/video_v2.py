"""
video_v2.py
───────────
Video_Agent V2 — multi-scene storyboard video generation (NIMBUS § 3 blueprint).

Where ``video_agent.py`` (V1) produces a single Veo clip from one prompt, V2
builds a richer, CapCut-style ad by composing several scenes:

1. **Director** — Gemini plans a scene-by-scene storyboard from the brief: each
   scene has a visual description, an on-screen subtitle line, and a duration.
2. **Keyframes** — Gemini's native image model renders one keyframe per scene at
   the resolved platform aspect ratio (Req 7.1). The keyframe anchors the scene.
3. **Scene clips** — Google Veo animates each keyframe into a short dynamic clip
   (image-to-video), so every scene has real motion rather than a static frame.
4. **Subtitles** — each clip gets its scene subtitle burnt in via ffmpeg
   ``drawtext`` (CapCut-style bottom caption with a translucent box).
5. **Transitions** — clips are stitched with ffmpeg ``xfade`` cross-dissolves for
   smooth auto-transitions.
6. **Voiceover** — one ElevenLabs narration track is scripted for the whole ad
   and mixed on top of the combined video.

No silent fallbacks for the core Veo step — if Veo is unavailable or fails, the
agent fails loudly (project convention). Every external call (Gemini, Veo,
ElevenLabs, ffmpeg, S3, Supabase) is wrapped in ``try/except`` with the
``[VideoAgentV2]`` logging prefix.

This module implements the shared ``generate(...)`` contract from ``base.py`` and
never imports the other three Media Agents (Req 5.2).
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, TypedDict

from shared.clients import gemini, s3, supabase
from shared.s3_client import upload_file_public
from config import S3_BUCKET_NAME, VERTEX_PROJECT_ID

from .base import AgentResult, load_guide

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

# Veo image-to-video minimum clip length (seconds).
_VEO_MIN_CLIP_SECONDS = 5
# Per-scene clip length we request from Veo (kept at the minimum to bound cost).
_SCENE_CLIP_SECONDS = 5
# Cross-dissolve duration between scenes (seconds).
_TRANSITION_SECONDS = 0.6
# Default / bounds on the number of storyboard scenes.
_DEFAULT_SCENES = 4
_MIN_SCENES = 2
_MAX_SCENES = 5
# Veo image-to-video model (lite variant per blueprint § 3A).
_VEO_MODEL = "veo-3.1-lite-generate-001"
# Native image model for keyframes.
# Primary: Imagen 4 (separate quota from Gemini, better for image gen).
# Fallback: Gemini Flash Lite (only if Imagen fails).
_IMAGE_MODEL_PRIMARY = "imagen-4.0-generate-001"
_IMAGE_MODEL_FALLBACK = "gemini-3.1-flash-lite-image"
# Max resolution for Imagen 4 keyframes.
_IMAGE_MAX_RESOLUTION = 1048
# Pause between keyframe calls to avoid burst 429s (RESOURCE_EXHAUSTED).
_KEYFRAME_THROTTLE_SECONDS = 3.0
# Retry policy for a rate-limited (429) keyframe request.
_KEYFRAME_MAX_ATTEMPTS = 3
_KEYFRAME_BACKOFF_SECONDS = 8.0


class Scene(TypedDict):
    """One storyboard scene planned by the Director (CapCut-style shot card)."""

    description: str  # visual scene description for the keyframe/clip
    shot_type: str  # e.g. "Close-up (CU)", "Medium shot (MS)", "Wide shot"
    camera_movement: str  # e.g. "slow push in", "handheld pan left", "static"
    subtitle: str  # on-screen caption text (burnt in)
    script: str  # per-scene voiceover / narration line
    sfx: str  # per-scene sound-effect plan (short description for SFX gen)
    duration: float  # target seconds for this scene


# ─── Malaysia localization (conditional by target audience) ──────────────────

# Base Malaysian vibe applied for ANY audience — setting/casting/tone only.
_LOCALIZATION_BASE = (
    "LOCALIZATION — MALAYSIA: This is a Malaysian ad for the local market. Reflect an "
    "authentic Malaysian vibe — recognisable local settings and props where relevant "
    "(mamak/kopitiam, pasar, kedai runcit, flats, LRT/MRT, local streets, tropical light). "
    "Copy/subtitles should feel local (Bahasa Melayu or natural Manglish is welcome)."
)

# Audience-specific cultural rules. These are applied conditionally (if/else) —
# NOT as a blanket ban — because each community has different sensitivities.
_LOCALIZATION_BY_ETHNICITY: dict[str, str] = {
    "malay": (
        "TARGET AUDIENCE — MALAY / MUSLIM (apply strict halal-friendly rules): "
        "Cast Malay Malaysians. Modest dress (cover aurat; no revealing clothing). "
        "NO pork, NO alcohol, NO gambling, no non-halal food or imagery. "
        "Respect Islamic values; wholesome, family-friendly framing. Baju kurung/baju melayu welcome; "
        "Bahasa Melayu copy preferred."
    ),
    "chinese": (
        "TARGET AUDIENCE — CHINESE MALAYSIAN: Cast Chinese Malaysians. "
        "Pork and alcohol are acceptable if relevant to the product. Festive themes like "
        "Chinese New Year (red/gold, reunion, prosperity) work well. Mandarin/English/Manglish copy is fine. "
        "Avoid content offensive to Chinese cultural norms (e.g. unlucky symbolism where inappropriate)."
    ),
    "indian": (
        "TARGET AUDIENCE — INDIAN MALAYSIAN: Cast Indian Malaysians. "
        "Avoid BEEF and beef imagery (Hindu sensitivity); vegetarian-friendly options are a plus. "
        "Festive themes like Deepavali (lights, kolam, vibrant colours) work well. "
        "Tamil/English/Manglish copy is fine. Respect Hindu cultural values."
    ),
    "all": (
        "TARGET AUDIENCE — MIXED (all Malaysian ethnicities): Cast a natural mix of Malay, "
        "Chinese, and Indian Malaysians across scenes. Keep it universally family-friendly and "
        "inclusive: avoid pork/beef/alcohol/gambling and keep dress modest so the ad is safe for "
        "Malay/Muslim, Chinese, and Indian audiences at once."
    ),
}


def _normalize_ethnicity(target_ethnicity: Optional[str]) -> str:
    """Map a free-form audience value to a known localization key.

    Recognises ``malay`` / ``chinese`` / ``indian``; everything else (including
    ``None``, ``"all"``, ``"mixed"``) falls back to the inclusive ``"all"`` rules.
    """
    value = (target_ethnicity or "all").strip().lower()
    if value in _LOCALIZATION_BY_ETHNICITY:
        return value
    if "malay" in value or "muslim" in value:
        return "malay"
    if "chinese" in value or "cina" in value:
        return "chinese"
    if "indian" in value or "tamil" in value:
        return "indian"
    return "all"


def _build_localization(target_ethnicity: Optional[str]) -> str:
    """Build the conditional localization instruction for the chosen audience.

    Combines the shared Malaysian-vibe base with the audience-specific cultural
    rules (halal only for Malay/Muslim, no-beef for Indian, etc.), so the
    prohibitions are applied via if/else rather than a one-size ban.

    Args:
        target_ethnicity: The target audience (``malay``/``chinese``/``indian``/
            ``all``; anything unknown → ``all``).

    Returns:
        The full localization instruction string for prompts.
    """
    key = _normalize_ethnicity(target_ethnicity)
    return f"{_LOCALIZATION_BASE} {_LOCALIZATION_BY_ETHNICITY[key]}"


# ─── Step 1: Director storyboard ──────────────────────────────────────────────


def _resolve_scene_count(rules: dict) -> int:
    """Decide how many scenes to plan, bounded by the platform duration ceiling.

    Each scene is ~``_SCENE_CLIP_SECONDS`` long, so the count is the platform
    ceiling divided by the clip length, clamped to ``[_MIN_SCENES, _MAX_SCENES]``.

    Args:
        rules: Resolved platform rule (may carry ``max_duration_seconds``).

    Returns:
        The number of scenes to generate.
    """
    max_duration = rules.get("max_duration_seconds") if rules else None
    if not max_duration or max_duration <= 0:
        return _DEFAULT_SCENES
    approx = int(float(max_duration) // _SCENE_CLIP_SECONDS)
    return max(_MIN_SCENES, min(_MAX_SCENES, approx or _DEFAULT_SCENES))


def _generate_storyboard(
    brief: str, rules: dict, scene_count: int, target_ethnicity: Optional[str] = None
) -> list[Scene]:
    """Ask Gemini (the Director) to plan a scene-by-scene storyboard.

    Returns a list of ``scene_count`` scenes with visual descriptions, subtitle
    lines, and durations. Localization is conditional on ``target_ethnicity``
    (halal rules only for Malay/Muslim, no-beef for Indian, etc.). The structure
    is hook-first: the opening 1–2 scenes are an attention-grabbing pattern
    interrupt (even playful/absurd) before the product is introduced. On any
    failure a single-shot storyboard from the brief is returned (Req 3.2).

    Args:
        brief: The user's ad brief.
        rules: Resolved platform sizing rules.
        scene_count: How many scenes to plan.
        target_ethnicity: Target audience for conditional localization.

    Returns:
        A list of :class:`Scene` dicts (length ``scene_count`` on success).
    """
    guide = load_guide("video")
    aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"
    localization = _build_localization(target_ethnicity)

    # Hook-first structure: dedicate the first scene(s) to a scroll-stopping hook.
    hook_scenes = 1 if scene_count <= 3 else 2

    director_prompt = f"""You are an award-winning short-form ad Director planning a TikTok/Reels video.

Break the following brief into EXACTLY {scene_count} sequential scenes for a {aspect_ratio} vertical video.

Brief: "{brief}"

{localization}

STRUCTURE — HOOK FIRST (very important for Reels/TikTok):
- The FIRST {hook_scenes} scene(s) are a HOOK: a scroll-stopping pattern interrupt that grabs attention in the
  first 1-2 seconds. It can be surprising, funny, exaggerated, or a little absurd/nonsensical — it does NOT need
  to show the product yet. Examples: an unexpected action, a bold question on screen, a relatable "wait, what?" moment.
- The MIDDLE scenes introduce and show the product and its key benefit.
- The FINAL scene is a clear call-to-action.
- Keep energy high and pacing snappy throughout.

For EACH scene provide these fields:
- "description": a vivid, dynamic visual scene description (subject, setting, lighting, motion). Follow the localization
  rules above. Hook scenes can be playful/absurd; product scenes focus on the product. No text overlays baked in.
- "shot_type": e.g. "Close-up (CU)", "Medium shot (MS)", "Wide shot (WS)", "Extreme close-up (ECU)".
- "camera_movement": e.g. "whip pan", "slow push in", "handheld follow", "tilt up", "static", "crash zoom".
- "subtitle": a SHORT punchy on-screen caption (max 8 words). Hook scenes get the most clickbaity/curious line.
- "script": ONE spoken voiceover line for this scene (max 20 words), matching the audience/localization.
- "sfx": a short sound-effect plan (e.g. "whoosh + record scratch", "sizzling wok", "crowd gasp"). A few words.
- "duration": target seconds (a number between 3 and 8; hook scenes can be short and punchy).

Reference guidelines: {guide[:300]}

Return ONLY a JSON array of {scene_count} objects with keys
"description", "shot_type", "camera_movement", "subtitle", "script", "sfx", "duration". No prose."""

    try:
        from google.genai import types as genai_types

        resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=director_prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        parsed = json.loads(resp.text)
        scenes = _coerce_scenes(parsed, scene_count)
        if scenes:
            logger.info("[VideoAgentV2] Director planned %d scene(s)", len(scenes))
            return scenes
        logger.warning("[VideoAgentV2] Director returned no usable scenes; using single-shot.")
    except Exception as e:
        logger.warning("[VideoAgentV2] Storyboard planning failed: %s. Using single-shot.", e)

    # Degrade to a single scene built from the brief.
    return [
        Scene(
            description=brief,
            shot_type="Medium shot (MS)",
            camera_movement="slow push in",
            subtitle="",
            script="",
            sfx="",
            duration=float(_SCENE_CLIP_SECONDS),
        )
    ]


def _coerce_scenes(parsed: object, scene_count: int) -> list[Scene]:
    """Validate/normalize the Director's JSON into a list of :class:`Scene`.

    Skips malformed entries and clamps durations. Returns at most
    ``scene_count`` scenes. Never raises.
    """
    if not isinstance(parsed, list):
        return []
    scenes: list[Scene] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        description = str(entry.get("description") or "").strip()
        if not description:
            continue
        subtitle = str(entry.get("subtitle") or "").strip()
        try:
            duration = float(entry.get("duration") or _SCENE_CLIP_SECONDS)
        except (TypeError, ValueError):
            duration = float(_SCENE_CLIP_SECONDS)
        duration = max(4.0, min(8.0, duration))
        scenes.append(
            Scene(
                description=description,
                shot_type=str(entry.get("shot_type") or "").strip(),
                camera_movement=str(entry.get("camera_movement") or "").strip(),
                subtitle=subtitle,
                script=str(entry.get("script") or "").strip(),
                sfx=str(entry.get("sfx") or "").strip(),
                duration=duration,
            )
        )
        if len(scenes) >= scene_count:
            break
    return scenes


# ─── Step 2: Keyframe images ──────────────────────────────────────────────────


def _generate_casting_card(
    brief: str,
    target_ethnicity: Optional[str],
    work_dir: Path,
) -> Optional[str]:
    """Pre-generate a casting portrait of the main character for visual reference.

    Uses Imagen 4 to create a high-quality studio portrait matching the audience/ethnicity.
    Returns the local path to the generated image, or None on failure.
    """
    ethnicity = _normalize_ethnicity(target_ethnicity)
    casting_prompt = (
        f"Studio portrait casting photo of a main actor for a commercial, local Malaysian, "
        f"matching the target audience profile: {ethnicity}. "
        "Facing the camera, neutral pleasant expression, clean studio backdrop, natural lighting, "
        "high contrast, 35mm photograph, realistic facial details, high-fidelity."
    )
    logger.info("[VideoAgentV2] Generating character casting card using Imagen 4...")
    kf_path = _try_imagen4_keyframe(casting_prompt, "3:4", work_dir, 999)
    if kf_path:
        return kf_path
    logger.warning("[VideoAgentV2] Casting card Imagen 4 failed; trying fallback.")
    return _try_gemini_keyframe(casting_prompt, "3:4", work_dir, None, 999)


def _analyze_casting_card(image_path: str) -> str:
    """Analyze the generated casting card with Gemini to get a detailed visual profile."""
    logger.info("[VideoAgentV2] Analyzing casting card for visual reverse-description...")
    try:
        from google.genai import types
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        analysis_prompt = (
            "Analyze the person in this casting photo. Return EXACTLY two sentences describing "
            "their physical appearance, age group, hair color/style/length, facial features, "
            "clothing type, and clothing color. Keep the description highly concrete and objective, "
            "avoiding subjective adjectives like 'beautiful' or 'charming'. "
            "Return only the description text, no labels, no conversational intro."
        )
        resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=[img_part, analysis_prompt],
        )
        profile = resp.text.strip()
        logger.info("[VideoAgentV2] Resolved character visual profile: %s", profile)
        return profile
    except Exception as e:
        logger.warning("[VideoAgentV2] Casting card analysis failed: %s. Using fallback profile.", e)
        return "A local Malaysian actor, matching the target audience profile."


def _generate_keyframe(
    scene: Scene,
    aspect_ratio: str,
    work_dir: Path,
    reference_parts: Optional[list],
    index: int,
    localization: str = "",
    char_profile: str = "",
    char_ref_path: Optional[str] = None,
) -> Optional[str]:
    """Render one keyframe image for a scene.

    Primary: Imagen 4 (``imagen-4.0-generate-001``) — separate quota from Gemini
    text models, designed for image generation, max 1048px resolution.
    Fallback: Gemini Flash Lite (only if Imagen fails/429s after retries).

    A rate-limited (429) request is retried with backoff up to
    ``_KEYFRAME_MAX_ATTEMPTS`` times per model. Returns the local ``.jpg`` path,
    or ``None`` on failure.
    """
    from google.genai import types

    prompt = (
        f"Commercial ad keyframe, {aspect_ratio}, {scene.get('shot_type') or 'medium shot'}"
        f"{', ' + scene['camera_movement'] if scene.get('camera_movement') else ''}. "
        f"{scene['description']} "
    )
    if char_profile:
        prompt += f"Featuring character: {char_profile}. "

    prompt += (
        "Clean modern composition, vibrant, high contrast, no text overlays, no watermark. "
        f"{localization}"
    )

    # Try Imagen 4 first (primary model).
    kf_path = _try_imagen4_keyframe(prompt, aspect_ratio, work_dir, index)
    if kf_path:
        return kf_path

    # Fallback to Gemini Flash Lite (with reference support).
    logger.info("[VideoAgentV2] Imagen 4 failed for keyframe %d; trying Gemini Flash Lite fallback.", index)
    combined_refs = list(reference_parts) if reference_parts else []
    if char_ref_path and os.path.exists(char_ref_path):
        try:
            with open(char_ref_path, "rb") as f:
                c_bytes = f.read()
            char_part = types.Part.from_bytes(data=c_bytes, mime_type="image/jpeg")
            combined_refs.append(char_part)
        except Exception as e:
            logger.warning("[VideoAgentV2] Failed to load character reference for fallback keyframe %d: %s", index, e)

    return _try_gemini_keyframe(prompt, aspect_ratio, work_dir, combined_refs, index)


def _try_imagen4_keyframe(
    prompt: str, aspect_ratio: str, work_dir: Path, index: int
) -> Optional[str]:
    """Generate a keyframe via Imagen 4. Returns path or None."""
    from google.genai import types

    # Map aspect ratio string to Imagen 4's accepted values.
    # Imagen 4 accepts: "1:1", "9:16", "16:9", "3:4", "4:3"
    imagen_aspect = aspect_ratio if aspect_ratio in ("1:1", "9:16", "16:9", "3:4", "4:3") else "9:16"

    for attempt in range(1, _KEYFRAME_MAX_ATTEMPTS + 1):
        try:
            response = gemini.models.generate_images(
                model=_IMAGE_MODEL_PRIMARY,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=imagen_aspect,
                    safety_filter_level="BLOCK_ONLY_HIGH",
                    person_generation="ALLOW_ADULT",
                ),
            )

            if response.generated_images:
                image = response.generated_images[0]
                if image.image and image.image.image_bytes:
                    kf_path = str(work_dir / f"keyframe_{index}_{uuid.uuid4().hex[:6]}.jpg")
                    with open(kf_path, "wb") as f:
                        f.write(image.image.image_bytes)
                    logger.info("[VideoAgentV2] Keyframe %d generated (Imagen 4): %s", index, kf_path)
                    return kf_path

            logger.warning("[VideoAgentV2] Imagen 4 keyframe %d: no image returned.", index)
            return None
        except Exception as e:
            message = str(e)
            is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
            if is_rate_limited and attempt < _KEYFRAME_MAX_ATTEMPTS:
                wait = _KEYFRAME_BACKOFF_SECONDS * attempt
                logger.warning(
                    "[VideoAgentV2] Imagen 4 keyframe %d rate-limited (attempt %d/%d); retrying in %.0fs",
                    index, attempt, _KEYFRAME_MAX_ATTEMPTS, wait,
                )
                time.sleep(wait)
                continue
            logger.warning("[VideoAgentV2] Imagen 4 keyframe %d failed: %s", index, e)
            return None
    return None


def _try_gemini_keyframe(
    prompt: str, aspect_ratio: str, work_dir: Path, reference_parts: Optional[list], index: int
) -> Optional[str]:
    """Generate a keyframe via Gemini Flash Lite (fallback). Returns path or None."""
    from google.genai import types

    contents: list = []
    if reference_parts:
        contents.append(
            "Use the reference image(s) as the visual anchor for the product/subject, "
            "preserving colors and materials, while composing this scene:"
        )
        contents.extend(reference_parts)
    contents.append(prompt)

    config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
            image_size="1K",
            output_mime_type="image/jpeg",
        ),
        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
    )

    for attempt in range(1, _KEYFRAME_MAX_ATTEMPTS + 1):
        try:
            response = gemini.models.generate_content(
                model=_IMAGE_MODEL_FALLBACK,
                contents=contents,
                config=config,
            )
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        kf_path = str(work_dir / f"keyframe_{index}_{uuid.uuid4().hex[:6]}.jpg")
                        with open(kf_path, "wb") as f:
                            f.write(part.inline_data.data)
                        logger.info("[VideoAgentV2] Keyframe %d generated (Gemini fallback): %s", index, kf_path)
                        return kf_path
            logger.warning("[VideoAgentV2] Gemini fallback keyframe %d: no image returned.", index)
            return None
        except Exception as e:
            message = str(e)
            is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
            if is_rate_limited and attempt < _KEYFRAME_MAX_ATTEMPTS:
                wait = _KEYFRAME_BACKOFF_SECONDS * attempt
                logger.warning(
                    "[VideoAgentV2] Gemini fallback keyframe %d rate-limited (attempt %d/%d); retrying in %.0fs",
                    index, attempt, _KEYFRAME_MAX_ATTEMPTS, wait,
                )
                time.sleep(wait)
                continue
            logger.warning("[VideoAgentV2] Gemini fallback keyframe %d failed: %s", index, e)
            return None
    return None


# ─── Step 3: Veo scene clips (image-to-video) ─────────────────────────────────


async def _generate_scene_clip(
    keyframe_path: str,
    scene: Scene,
    aspect_ratio: str,
    work_dir: Path,
    index: int,
) -> Optional[str]:
    """Animate a keyframe into a short dynamic clip via Google Veo (image-to-video).

    Uses the keyframe as the first frame and Veo's motion synthesis to produce a
    silent clip (audio is added later as a single voiceover). Returns the local
    ``.mp4`` path, or ``None`` on failure.
    """
    if not VERTEX_PROJECT_ID:
        logger.warning("[VideoAgentV2] VERTEX_PROJECT_ID not set — cannot generate clip.")
        return None

    def _blocking_clip_call() -> Optional[bytes]:
        try:
            from google import genai
            from google.genai import types

            veo_client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT_ID,
                location="us-central1",
            )

            with open(keyframe_path, "rb") as f:
                start_bytes = f.read()
            start_image = types.Image(image_bytes=start_bytes, mime_type="image/jpeg")

            source = types.GenerateVideosSource(
                image=start_image,
                prompt=(
                    f"{scene['description']} "
                    f"Shot: {scene.get('shot_type') or 'medium shot'}. "
                    f"Camera: {scene.get('camera_movement') or 'smooth cinematic movement'}. "
                    "Maintain product focus, scene continuity, and an authentic Malaysian setting."
                ),
            )
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                number_of_videos=1,
                duration_seconds=_SCENE_CLIP_SECONDS,
                person_generation="allow_adult",
                generate_audio=False,
            )

            logger.info("[VideoAgentV2] Submitting Veo clip %d (%ds)", index, _SCENE_CLIP_SECONDS)
            operation = veo_client.models.generate_videos(
                model=_VEO_MODEL,
                source=source,
                config=config,
            )
            while not operation.done:
                logger.info("[VideoAgentV2] Veo clip %d in progress... polling in 10s.", index)
                time.sleep(10)
                operation = veo_client.operations.get(operation)

            response = operation.result
            if not response or not response.generated_videos:
                logger.error("[VideoAgentV2] Veo clip %d returned no video.", index)
                return None
            video = response.generated_videos[0]
            if not video.video or not video.video.video_bytes:
                logger.error("[VideoAgentV2] Veo clip %d has no bytes.", index)
                return None
            return video.video.video_bytes
        except Exception as e:
            logger.error("[VideoAgentV2] Veo clip %d call failed: %s", index, e)
            return None

    try:
        clip_bytes = await asyncio.to_thread(_blocking_clip_call)
    except Exception as e:
        logger.error("[VideoAgentV2] asyncio.to_thread error for clip %d: %s", index, e)
        return None

    if not clip_bytes:
        return None

    clip_path = str(work_dir / f"scene_{index}_{uuid.uuid4().hex[:6]}.mp4")
    with open(clip_path, "wb") as f:
        f.write(clip_bytes)
    logger.info("[VideoAgentV2] Veo clip %d saved: %s", index, clip_path)
    return clip_path


# ─── Step 4: Burn subtitles (CapCut-style) ────────────────────────────────────


def _burn_subtitle(clip_path: str, subtitle: str, work_dir: Path, index: int) -> str:
    """Burn a scene subtitle into a clip via ffmpeg ``drawtext``.

    The subtitle is written to a sidecar text file and referenced with
    ``textfile=`` so arbitrary punctuation needs no shell escaping. A translucent
    box is drawn behind the text (CapCut-style bottom caption). Returns the
    captioned clip path, or the original ``clip_path`` when there is no subtitle
    or the ffmpeg call fails (best-effort — the clip is still usable).
    """
    if not subtitle:
        return clip_path

    txt_path = work_dir / f"subtitle_{index}.txt"
    try:
        txt_path.write_text(subtitle, encoding="utf-8")
    except Exception as e:
        logger.warning("[VideoAgentV2] Could not write subtitle file %d: %s", index, e)
        return clip_path

    out_path = str(work_dir / f"scene_{index}_captioned.mp4")
    # Escape backslashes and colons in the path for the ffmpeg filter argument.
    ff_txt = str(txt_path).replace("\\", "/").replace(":", "\\:")
    drawtext = (
        f"drawtext=textfile='{ff_txt}':"
        "fontcolor=white:fontsize=h/22:"
        "box=1:boxcolor=black@0.5:boxborderw=18:"
        "x=(w-text_w)/2:y=h-(h/8)-text_h:"
        "line_spacing=6"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", clip_path,
        "-vf", drawtext,
        "-c:a", "copy",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Burnt subtitle into scene %d", index)
        return out_path
    except Exception as e:
        logger.warning("[VideoAgentV2] Subtitle burn failed for scene %d: %s", index, e)
        return clip_path


# ─── Step 5: Combine with xfade transitions ───────────────────────────────────


def _probe_duration(clip_path: str) -> float:
    """Return a clip's duration in seconds via ffprobe, or ``_SCENE_CLIP_SECONDS``.

    Best-effort: any failure returns the nominal per-scene length so the xfade
    offset math still produces a valid (if approximate) transition.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                clip_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return float(result.stdout.decode().strip())
    except Exception:
        return float(_SCENE_CLIP_SECONDS)


def _concat_with_transitions(clips: list[str], work_dir: Path) -> str:
    """Stitch scene clips into one video with ``xfade`` cross-dissolves.

    Builds an ffmpeg ``filter_complex`` that chains each successive clip with an
    ``xfade`` transition, computing the offset from the accumulated (overlapping)
    duration. A single clip is returned unchanged. On ffmpeg failure, falls back
    to a plain concat-demuxer join (no transitions) so a video is still produced.

    Args:
        clips: Ordered list of (captioned) scene clip paths.
        work_dir: Working directory for intermediate/output files.

    Returns:
        The combined video path.
    """
    if len(clips) == 1:
        return clips[0]

    out_path = str(work_dir / "combined.mp4")
    durations = [_probe_duration(c) for c in clips]

    # Build the xfade chain. Each step overlaps the previous output tail by
    # _TRANSITION_SECONDS, so the running offset subtracts the transition time.
    inputs: list[str] = []
    for clip in clips:
        inputs.extend(["-i", clip])

    filter_parts: list[str] = []
    prev_label = "0:v"
    offset = durations[0] - _TRANSITION_SECONDS
    for i in range(1, len(clips)):
        out_label = f"v{i}" if i < len(clips) - 1 else "vout"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:"
            f"duration={_TRANSITION_SECONDS}:offset={max(0.0, offset):.3f}[{out_label}]"
        )
        prev_label = out_label
        offset += durations[i] - _TRANSITION_SECONDS

    filter_complex = ";".join(filter_parts)
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Combined %d clips with xfade transitions", len(clips))
        return out_path
    except Exception as e:
        logger.warning("[VideoAgentV2] xfade concat failed: %s. Falling back to plain concat.", e)
        return _concat_plain(clips, work_dir)


def _concat_plain(clips: list[str], work_dir: Path) -> str:
    """Join clips end-to-end via the ffmpeg concat demuxer (no transitions).

    A robust fallback when the ``xfade`` filter graph fails. Returns the joined
    path, or the first clip if even the plain concat fails.
    """
    list_file = work_dir / "concat_list.txt"
    try:
        lines = [f"file '{Path(c).as_posix()}'" for c in clips]
        list_file.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        logger.error("[VideoAgentV2] Could not write concat list: %s", e)
        return clips[0]

    out_path = str(work_dir / "combined_plain.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Combined %d clips via plain concat", len(clips))
        return out_path
    except Exception as e:
        logger.error("[VideoAgentV2] Plain concat failed: %s. Using first clip only.", e)
        return clips[0]


# ─── Step 6: Voiceover ────────────────────────────────────────────────────────


def _script_voiceover(brief: str, scenes: list[Scene]) -> str:
    """Stitch the per-scene scripts into one continuous localized voiceover.

    Prefers each scene's own ``script`` line (planned by the Director, already
    localized for Malaysia); falls back to subtitles, then the brief. The result
    is lightly smoothed by Gemini so the beats flow as one narration.
    """
    # Prefer the per-scene scripts; fall back to subtitles.
    beats = [s.get("script") or s.get("subtitle") or "" for s in scenes]
    beats_text = " / ".join(b for b in beats if b)

    try:
        resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Combine these per-scene ad script beats into ONE smooth, punchy commercial "
                "voiceover for the Malaysian market (Bahasa Melayu or natural Manglish, warm and local). "
                f"Keep it under 50 words total. Beats: {beats_text or brief}. "
                f"Product brief: {brief}. Output only the spoken words, no quotes, no scene labels."
            ),
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning("[VideoAgentV2] Voiceover scripting failed: %s. Using beats/brief.", e)
        return (beats_text or brief)[:200]


def _generate_voiceover(
    brief: str, scenes: list[Scene], work_dir: Path,
    target_ethnicity: Optional[str] = None, gender: Optional[str] = None,
) -> Optional[str]:
    """Generate one ElevenLabs narration track for the full ad.

    Selects the voice matching the target audience + gender via ``VOICE_CONFIG``.
    """
    from shared.elevenlabs_utils import generate_tts
    from config import VOICE_CONFIG, DEFAULT_VOICE

    ethnicity_key = _normalize_ethnicity(target_ethnicity)
    voice_gender = (gender or "female").strip().lower()
    if voice_gender not in ("male", "female"):
        voice_gender = "female"

    voice_entry = VOICE_CONFIG.get(
        ("malaysia", ethnicity_key, voice_gender),
        DEFAULT_VOICE,
    )
    voice_id = voice_entry["voice_id"]
    lang_code = voice_entry.get("lang", "ms")

    vo_text = _script_voiceover(brief, scenes)
    vo_path = str(work_dir / "voiceover.mp3")
    ok = generate_tts(
        vo_text,
        vo_path,
        voice_id=voice_id,
        language_code=lang_code,
    )
    if ok:
        logger.info(
            "[VideoAgentV2] Voiceover generated (audience=%s, voice=%s): %s",
            ethnicity_key, voice_id[:8], vo_text[:60],
        )
        return vo_path
    logger.warning("[VideoAgentV2] Voiceover TTS failed.")
    return None


def _generate_sfx_bed(scenes: list[Scene], work_dir: Path) -> Optional[str]:
    """Generate a per-scene SFX bed and concatenate it into one track.

    Each scene's ``sfx`` plan is rendered by ElevenLabs at that scene's duration,
    then the clips are joined in scene order into a single ``sfx_bed.mp3`` that
    roughly tracks the video timeline. Returns the bed path, or ``None`` when no
    scene had an SFX plan or generation failed (best-effort — the ad still gets
    its voiceover).
    """
    from shared.elevenlabs_utils import generate_sfx

    sfx_parts: list[str] = []
    for i, scene in enumerate(scenes):
        sfx_prompt = (scene.get("sfx") or "").strip()
        if not sfx_prompt:
            continue
        part_path = str(work_dir / f"sfx_{i}.mp3")
        ok = generate_sfx(sfx_prompt, part_path, duration_seconds=float(scene.get("duration") or _SCENE_CLIP_SECONDS))
        if ok and os.path.exists(part_path):
            sfx_parts.append(part_path)

    if not sfx_parts:
        return None
    if len(sfx_parts) == 1:
        return sfx_parts[0]

    # Concatenate the per-scene SFX clips into one bed via ffmpeg concat demuxer.
    list_file = work_dir / "sfx_list.txt"
    try:
        list_file.write_text("\n".join(f"file '{Path(p).as_posix()}'" for p in sfx_parts), encoding="utf-8")
    except Exception as e:
        logger.warning("[VideoAgentV2] Could not write SFX list: %s", e)
        return sfx_parts[0]

    bed_path = str(work_dir / "sfx_bed.mp3")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        bed_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Built SFX bed from %d scene(s)", len(sfx_parts))
        return bed_path
    except Exception as e:
        logger.warning("[VideoAgentV2] SFX bed concat failed: %s. Using first SFX clip.", e)
        return sfx_parts[0]


def _merge_audio(video_path: str, vo_path: Optional[str], sfx_bed: Optional[str], out_path: str) -> bool:
    """Mux voiceover (foreground) + SFX bed (lowered) onto the silent video.

    Handles any combination: VO only, SFX only, or both (mixed with ffmpeg
    ``amix``, SFX ducked under the VO). Returns ``True`` on success; ``False``
    leaves the caller to fall back to the video as-is.
    """
    if not vo_path and not sfx_bed:
        return False

    try:
        if vo_path and sfx_bed:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", vo_path,
                "-i", sfx_bed,
                "-filter_complex",
                "[1:a]volume=1.0[vo];[2:a]volume=0.35[sfx];[vo][sfx]amix=inputs=2:duration=first[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                out_path,
            ]
        else:
            audio = vo_path or sfx_bed
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                out_path,
            ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Merged audio (vo=%s, sfx=%s)", bool(vo_path), bool(sfx_bed))
        return True
    except Exception as e:
        logger.warning("[VideoAgentV2] Audio merge failed: %s. Using video without added audio.", e)
        return False


def _merge_voiceover(video_path: str, vo_path: str, out_path: str) -> bool:
    """Overlay the voiceover onto the (silent) combined video via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", vo_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info("[VideoAgentV2] Voiceover merged onto combined video.")
        return True
    except Exception as e:
        logger.warning("[VideoAgentV2] Voiceover merge failed: %s. Using video without VO.", e)
        return False


# ─── Supabase recording ───────────────────────────────────────────────────────


def _record_generated_ad(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    prompt_used: str,
    s3_key: Optional[str],
    status: str,
    metadata: dict,
) -> Optional[str]:
    """Insert a ``generated_ads`` row and return its id (best-effort)."""
    try:
        response = (
            supabase.table("generated_ads")
            .insert(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "media_type": "video",
                    "platform": platform,
                    "prompt_used": prompt_used,
                    "s3_media_key": s3_key,
                    "status": status,
                    "metadata": metadata,
                }
            )
            .execute()
        )
        rows = response.data or []
        ad_id = rows[0].get("id") if rows else None
        logger.info("[VideoAgentV2] Recorded generated_ads row (status=%s, id=%s)", status, ad_id)
        return ad_id
    except Exception as e:
        logger.error("[VideoAgentV2] Supabase recording failed (status=%s): %s", status, e)
        return None


# ─── Two-phase (plan → approve → execute) API ────────────────────────────────


async def plan_video(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: dict,
    reference_parts: Optional[list] = None,
    target_ethnicity: Optional[str] = None,
) -> dict:
    """Phase 1 — plan the storyboard and render keyframes for user review.

    Runs the Director and generates one keyframe per scene, uploading each
    keyframe to S3 so it survives until the user approves. Does NOT call Veo
    (the expensive step). The returned plan is meant to be shown on the canvas
    with a "Continue" button; passing it back to :func:`execute_video_plan`
    resumes generation without re-planning or re-rendering keyframes.

    Keyframes are throttled between calls to avoid burst rate-limits (429).

    Args:
        brief: The creative/product prompt.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: Normalized target platform.
        rules: Resolved platform sizing rules.
        reference_parts: Optional multimodal reference parts.

    Returns:
        A plan dict: ``{plan_id, brief, platform, aspect_ratio, scenes:[{index,
        description, subtitle, duration, keyframe_s3_key, keyframe_url}]}``.
        Scenes whose keyframe failed are omitted. Raises when no keyframe could
        be produced at all (so the caller surfaces a loud failure).
    """
    if not VERTEX_PROJECT_ID:
        raise RuntimeError(
            "VERTEX_PROJECT_ID is not configured. Video V2 requires Google Veo."
        )

    plan_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.mkdtemp(prefix="video_v2_plan_"))
    try:
        aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"
        scene_count = _resolve_scene_count(rules)
        scenes = _generate_storyboard(brief, rules, scene_count, target_ethnicity)
        localization = _build_localization(target_ethnicity)

        # Character casting phase
        char_ref_path = _generate_casting_card(brief, target_ethnicity, work_dir)
        char_profile = ""
        char_ref_url = None
        char_ref_key = None
        if char_ref_path and os.path.exists(char_ref_path):
            char_profile = _analyze_casting_card(char_ref_path)
            char_ref_key = f"generated_ads/{project_id}/{task_id}/plans/{plan_id}/character_reference.jpg"
            try:
                char_ref_url = upload_file_public(char_ref_path, char_ref_key)
                logger.info("[VideoAgentV2] Uploaded casting reference card: %s", char_ref_url)
            except Exception as e:
                logger.warning("[VideoAgentV2] Failed to upload casting card: %s", e)

        planned: list[dict] = []
        for i, scene in enumerate(scenes):
            keyframe = _generate_keyframe(
                scene, aspect_ratio, work_dir, reference_parts, i, localization, char_profile, char_ref_path
            )
            if not keyframe:
                logger.warning("[VideoAgentV2] Plan: scene %d has no keyframe; omitting.", i)
                continue
            # Persist the keyframe to S3 so execute can fetch it after approval.
            kf_key = (
                f"generated_ads/{project_id}/{task_id}/plans/{plan_id}/keyframe_{i}.jpg"
            )
            try:
                kf_url = upload_file_public(keyframe, kf_key)
            except Exception as e:
                logger.warning("[VideoAgentV2] Plan: keyframe %d upload failed: %s", i, e)
                continue
            planned.append(
                {
                    "index": i,
                    "description": scene["description"],
                    "shot_type": scene.get("shot_type", ""),
                    "camera_movement": scene.get("camera_movement", ""),
                    "subtitle": scene["subtitle"],
                    "script": scene.get("script", ""),
                    "sfx": scene.get("sfx", ""),
                    "duration": scene["duration"],
                    "keyframe_s3_key": kf_key,
                    "keyframe_url": kf_url,
                }
            )
            # Throttle to avoid burst 429s across successive image calls.
            if i < len(scenes) - 1:
                time.sleep(_KEYFRAME_THROTTLE_SECONDS)

        if not planned:
            raise RuntimeError(
                "Video V2 planning produced no keyframes. Check Gemini image quota "
                "(429 RESOURCE_EXHAUSTED) and credentials."
            )

        logger.info("[VideoAgentV2] Plan %s ready with %d scene(s)", plan_id, len(planned))
        return {
            "plan_id": plan_id,
            "brief": brief,
            "platform": platform,
            "aspect_ratio": aspect_ratio,
            "target_ethnicity": _normalize_ethnicity(target_ethnicity),
            "gender": "female",  # default; overridden by caller context
            "character_reference_url": char_ref_url,
            "character_profile": char_profile,
            "scenes": planned,
        }
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)


async def execute_video_plan(
    *,
    plan: dict,
    project_id: str,
    task_id: str,
    platform: str,
) -> AgentResult:
    """Phase 2 — turn an approved plan into the final video.

    Downloads each approved keyframe from S3, animates it with Veo, burns in the
    scene subtitle, stitches the clips with cross-dissolves, adds one voiceover,
    uploads the result, and records a ``generated_ads`` row. This is the
    expensive phase and only runs after the user clicks "Continue".

    Args:
        plan: The plan dict returned by :func:`plan_video` (and possibly edited
            by the user — subtitles/descriptions are honored as-is).
        project_id: Owning project id.
        task_id: Owning task id.
        platform: Normalized target platform.

    Returns:
        An :class:`AgentResult` for the produced (or failed) video.
    """
    logger.info("[VideoAgentV2] Executing approved plan %s", plan.get("plan_id"))
    work_dir: Optional[Path] = None
    brief = str(plan.get("brief") or "")
    aspect_ratio = str(plan.get("aspect_ratio") or "9:16")
    plan_scenes = plan.get("scenes") or []

    try:
        if not plan_scenes:
            raise RuntimeError("Approved plan has no scenes to execute.")

        work_dir = Path(tempfile.mkdtemp(prefix="video_v2_exec_"))
        scenes: list[Scene] = []
        captioned_clips: list[str] = []

        for entry in plan_scenes:
            if not isinstance(entry, dict):
                continue
            i = int(entry.get("index", len(scenes)))
            scene = Scene(
                description=str(entry.get("description") or ""),
                shot_type=str(entry.get("shot_type") or ""),
                camera_movement=str(entry.get("camera_movement") or ""),
                subtitle=str(entry.get("subtitle") or ""),
                script=str(entry.get("script") or ""),
                sfx=str(entry.get("sfx") or ""),
                duration=float(entry.get("duration") or _SCENE_CLIP_SECONDS),
            )
            scenes.append(scene)

            kf_key = entry.get("keyframe_s3_key")
            if not kf_key:
                logger.warning("[VideoAgentV2] Exec: scene %d missing keyframe key; skipping.", i)
                continue
            local_kf = str(work_dir / f"keyframe_{i}.jpg")
            try:
                s3.download_file(S3_BUCKET_NAME, kf_key, local_kf)
            except Exception as e:
                logger.warning("[VideoAgentV2] Exec: keyframe %d download failed: %s", i, e)
                continue

            clip = await _generate_scene_clip(local_kf, scene, aspect_ratio, work_dir, i)
            if not clip:
                logger.warning("[VideoAgentV2] Exec: scene %d produced no Veo clip.", i)
                continue
            captioned = _burn_subtitle(clip, scene["subtitle"], work_dir, i)
            captioned_clips.append(captioned)

        if not captioned_clips:
            raise RuntimeError(
                "Video V2 execution produced no scene clips. Check Veo credentials/quota."
            )

        combined = _concat_with_transitions(captioned_clips, work_dir)

        # Audio: per-scene SFX bed + one localized voiceover, mixed onto the video.
        final_path = combined
        plan_ethnicity = str(plan.get("target_ethnicity") or "all")
        plan_gender = str(plan.get("gender") or "female")
        vo_path = _generate_voiceover(brief, scenes, work_dir, plan_ethnicity, plan_gender)
        sfx_bed = _generate_sfx_bed(scenes, work_dir)
        if vo_path or sfx_bed:
            merged = str(work_dir / "final_with_audio.mp4")
            if _merge_audio(combined, vo_path, sfx_bed, merged):
                final_path = merged

        if not final_path or not os.path.exists(final_path):
            raise RuntimeError("Video V2 execution produced no output file.")

        s3_key = f"generated_ads/{project_id}/{task_id}/video_v2_{uuid.uuid4().hex[:6]}.mp4"
        try:
            s3_url = upload_file_public(final_path, s3_key)
        except Exception as e:
            logger.warning("[VideoAgentV2] Exec: S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=s3_key,
            status="completed",
            metadata={
                "s3_url": s3_url,
                "aspect_ratio": aspect_ratio,
                "generation_method": "veo_multi_scene_v2",
                "scene_count": len(captioned_clips),
                "scenes": [dict(s) for s in scenes],
                "plan_id": plan.get("plan_id"),
                "independent": True,
            },
        )

        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=None,
            status="completed",
            error=None,
        )

    except Exception as e:
        logger.error("[VideoAgentV2] Plan execution failed: %s", e)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=None,
            status="failed",
            metadata={"error": str(e), "generation_method": "veo_multi_scene_v2"},
        )
        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        if work_dir is not None:
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Public contract ──────────────────────────────────────────────────────────


async def generate(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: dict,
    reference_parts: Optional[list] = None,
    target_ethnicity: Optional[str] = None,
    gender: Optional[str] = None,
) -> AgentResult:
    """Generate one multi-scene storyboard video ad and record it.

    Pipeline: Director storyboard → per-scene keyframes → Veo image-to-video
    clips → burnt-in subtitles → xfade transitions → voiceover merge → S3.
    Veo is required (no silent fallback); if it produces no clips the agent
    fails loudly and records a ``failed`` row (Req 5.5).

    Args:
        brief: The creative/product prompt for the ad.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: Normalized target platform (e.g. ``"tiktok"``).
        rules: Resolved ``PlatformRule`` sizing (aspect ratio + duration).
        reference_parts: Optional multimodal reference parts (used to anchor
            keyframes to the user's product image).

    Returns:
        An :class:`AgentResult` describing the generated (or failed) output.
    """
    logger.info("[VideoAgentV2] Starting multi-scene video generation for '%s'", platform)
    work_dir: Optional[Path] = None

    try:
        if not VERTEX_PROJECT_ID:
            raise RuntimeError(
                "VERTEX_PROJECT_ID is not configured. Video V2 requires Google Veo. "
                "Set VERTEX_PROJECT_ID in backend/.env to enable video generation."
            )

        work_dir = Path(tempfile.mkdtemp(prefix="video_v2_"))
        aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"

        # 1. Director storyboard.
        scene_count = _resolve_scene_count(rules)
        scenes = _generate_storyboard(brief, rules, scene_count, target_ethnicity)
        localization = _build_localization(target_ethnicity)

        # 2 + 3. For each scene: keyframe → Veo clip → subtitle burn.
        captioned_clips: list[str] = []
        for i, scene in enumerate(scenes):
            keyframe = _generate_keyframe(
                scene, aspect_ratio, work_dir, reference_parts, i, localization
            )
            if not keyframe:
                logger.warning("[VideoAgentV2] Scene %d skipped (no keyframe).", i)
                continue
            clip = await _generate_scene_clip(keyframe, scene, aspect_ratio, work_dir, i)
            if not clip:
                logger.warning("[VideoAgentV2] Scene %d skipped (no Veo clip).", i)
                continue
            captioned = _burn_subtitle(clip, scene["subtitle"], work_dir, i)
            captioned_clips.append(captioned)

        if not captioned_clips:
            raise RuntimeError(
                "Video V2 produced no scene clips. Check VERTEX_PROJECT_ID, GCP "
                "credentials, and that the Veo API is enabled in your project."
            )
        # 4 + 5. Combine with transitions.
        combined = _concat_with_transitions(captioned_clips, work_dir)

        # 6. Audio: per-scene SFX bed + one localized voiceover.
        final_path = combined
        vo_path = _generate_voiceover(brief, scenes, work_dir, target_ethnicity, gender)
        sfx_bed = _generate_sfx_bed(scenes, work_dir)
        if vo_path or sfx_bed:
            merged = str(work_dir / "final_with_audio.mp4")
            if _merge_audio(combined, vo_path, sfx_bed, merged):
                final_path = merged

        if not final_path or not os.path.exists(final_path):
            raise RuntimeError("Video V2 produced no output file.")

        # Upload to S3.
        s3_key = f"generated_ads/{project_id}/{task_id}/video_v2_{uuid.uuid4().hex[:6]}.mp4"
        try:
            s3_url = upload_file_public(final_path, s3_key)
        except Exception as e:
            logger.warning("[VideoAgentV2] S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=s3_key,
            status="completed",
            metadata={
                "s3_url": s3_url,
                "aspect_ratio": aspect_ratio,
                "generation_method": "veo_multi_scene_v2",
                "scene_count": len(captioned_clips),
                "scenes": [dict(s) for s in scenes],
                "independent": True,
            },
        )

        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=None,
            status="completed",
            error=None,
        )

    except Exception as e:
        logger.error("[VideoAgentV2] Generation failed: %s", e)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=None,
            status="failed",
            metadata={"error": str(e), "generation_method": "veo_multi_scene_v2"},
        )
        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        if work_dir is not None:
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)
