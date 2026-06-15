import os
import json
import base64
import logging
import subprocess
import tempfile
import time
import uuid
import requests
import numpy as np
from pathlib import Path
from PIL import Image
from google.genai import types
from agent.clients import gemini, elevenlabs, qdrant, FLUXAI_API_KEY
from agent.prompts import SCULPT_PROMPT_TEMPLATE
from config import VOICE_CONFIG, DEFAULT_VOICE
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def _to_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _make_binary_mask(segmented_overlay_path):
    """Convert CLIPSeg overlay → binary mask (white=edit, black=keep)."""
    img = Image.open(segmented_overlay_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    mask = (alpha > 50).astype(np.uint8) * 255
    mask_img = Image.fromarray(mask, mode="L")
    mask_path = segmented_overlay_path.replace("segmented_", "mask_")
    mask_img.save(mask_path)
    return mask_path


def _enhance_prompt_for_imagen(violations, market, platform, ethnicity, age_group, feedback=""):
    """Gemini converts violations → short Imagen-optimized inpainting prompt."""
    raw = json.dumps(violations)

    response = gemini.models.generate_content(
        model="gemini-3-flash-preview",
        contents=f"""Convert these compliance violations into a SHORT image inpainting prompt.

                    Describe what should APPEAR in the masked region (not what to remove).

                    Violations: {raw}
                    Target: {market}, {ethnicity} audience, {age_group}, platform: {platform}
                    {f"Previous feedback: {feedback}" if feedback else ""}

                    Platform style guide:
                    - TikTok: vibrant, trendy, Gen Z aesthetic, bold colors
                    - Meta/Instagram: clean, professional, lifestyle photography
                    - YouTube: cinematic, high quality, broad appeal

                    Rules:
                    - Max 50 words
                    - Positive description only (what TO show)
                    - Match the platform aesthetic
                    - Professional advertising quality

                    Return ONLY the prompt text.""",
    )
    return response.text.strip()


# ── Platform style mappings for SCULPT prompts ────────────────────────────────
_PLATFORM_STYLES = {
    "tiktok": {
        "description": "TikTok: vibrant, trendy, Gen Z aesthetic, bold colors, eye-catching visuals",
        "keywords": ["vibrant", "trendy"],
    },
    "meta": {
        "description": "Meta/Instagram: clean, professional, lifestyle photography, polished look",
        "keywords": ["clean", "professional"],
    },
    "instagram": {
        "description": "Instagram: aspirational, lifestyle-focused, high quality, aesthetic",
        "keywords": ["clean", "professional"],
    },
    "youtube": {
        "description": "YouTube: cinematic, high quality, broad appeal, dynamic visuals",
        "keywords": ["cinematic", "high quality"],
    },
}

_DEFAULT_PLATFORM_STYLE = {
    "description": "General advertising: professional, appealing, brand-appropriate",
    "keywords": ["professional", "appealing"],
}


def _build_sculpt_prompt(
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
) -> str:
    """Generate a SCULPT framework image editing prompt via Gemini.

    Uses the SCULPT framework (Subject, Context, Use, Look, Photographic, Technical)
    to create a precise editing prompt optimized for image inpainting.

    Args:
        violations: List of compliance violation descriptions to fix.
        market: Target market (e.g. "malaysia", "singapore").
        platform: Advertising platform (e.g. "tiktok", "meta").
        ethnicity: Target ethnicity for cultural context.
        age_group: Target age group.

    Returns:
        A structured SCULPT prompt string for image editing.
    """
    platform_key = platform.lower().strip()
    style_info = _PLATFORM_STYLES.get(platform_key, _DEFAULT_PLATFORM_STYLE)

    platform_style = style_info["description"]
    platform_keywords = style_info["keywords"]
    platform_keywords_instruction = (
        f"Include these platform-specific style keywords: {', '.join(platform_keywords)}"
    )

    violations_text = json.dumps(violations, indent=2)

    prompt_input = SCULPT_PROMPT_TEMPLATE.format(
        violations=violations_text,
        market=market,
        platform=platform,
        ethnicity=ethnicity,
        age_group=age_group,
        platform_style=platform_style,
        platform_keywords_instruction=platform_keywords_instruction,
    )

    try:
        response = gemini.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt_input,
        )
        sculpt_prompt = response.text.strip()
        logger.info(f"SCULPT prompt generated for {platform}/{market} ({len(sculpt_prompt)} chars)")
        return sculpt_prompt
    except Exception as e:
        logger.error(f"SCULPT prompt generation failed: {e}")
        # Fallback: construct a basic prompt manually with all required components
        fallback = (
            f"[Subject] Replace non-compliant region with culturally appropriate content "
            f"addressing: {'; '.join(violations)}. "
            f"[Context] {platform_style}, targeting {ethnicity} audience in {market}. "
            f"[Use] Advertising compliance fix for {platform} platform, {age_group} demographic. "
            f"[Look] Match original image style, {', '.join(platform_keywords)} aesthetic. "
            f"[Photographic] Maintain lighting direction, match perspective and depth of field. "
            f"[Technical] High resolution output, preserve sharp edges, no text, "
            f"maintain lighting direction."
        )
        logger.warning("Using fallback SCULPT prompt due to Gemini failure")
        return fallback


@tool
def edit_image(
    image_path: str,
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    feedback: str = "",
) -> dict:
    """Fix compliance violations in an image using Imagen 4 inpainting with Flux Kontext Pro fallback.

    Flow: SCULPT prompt → Imagen 4 attempt → quality check → fallback to Flux if needed → save.

    Args:
        image_path: Path to the source image to edit.
        violations: List of compliance violation descriptions to fix.
        market: Target market (e.g. "malaysia", "singapore").
        platform: Target platform (e.g. "tiktok", "meta").
        ethnicity: Target ethnicity for cultural context.
        age_group: Target age group.
        feedback: Optional reviewer feedback for the edit.

    Returns:
        Dict with output_path, model_used, quality_score, and prompt_used on success,
        or error dict with original image path preserved on failure.
    """
    os.makedirs("assets/edits", exist_ok=True)
    output_filename = f"edited_{int(time.time())}_{os.path.basename(image_path)}"
    output_path = f"assets/edits/{output_filename}"

    # Step 1: Generate SCULPT prompt
    sculpt_prompt = _build_sculpt_prompt(violations, market, platform, ethnicity, age_group)
    if feedback:
        sculpt_prompt += f" Additional guidance: {feedback}"
    logger.info(f"SCULPT prompt generated ({len(sculpt_prompt)} chars)")

    # Step 2: Attempt Imagen 4 inpainting via Vertex AI
    imagen_success = False
    quality_score = 0
    model_used = ""

    try:
        logger.info("Attempting Imagen 4 (imagen-4.0-generate-preview) inpainting...")
        image_b64 = _to_base64(image_path)

        response = gemini.models.generate_images(
            model="imagen-4.0-generate-preview",
            prompt=sculpt_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                reference_images=[
                    types.RawReferenceImage(
                        reference_image=types.Image(
                            image_bytes=base64.b64decode(image_b64),
                        ),
                        reference_id=1,
                        reference_type="STYLE",
                    ),
                ],
            ),
        )

        # Extract result image
        if response.generated_images and len(response.generated_images) > 0:
            result_image = response.generated_images[0]
            with open(output_path, "wb") as f:
                f.write(result_image.image.image_bytes)
            logger.info(f"Imagen 4 result saved to {output_path}")

            # Step 3: Run quality check (Gemini vision comparison, score 0-100)
            quality_result = check_edit_quality.invoke(
                {"original_path": image_path, "edited_path": output_path}
            )

            if "error" not in quality_result:
                quality_score = quality_result.get("quality_score", 0)
                logger.info(f"Quality check score: {quality_score}/100")

                if quality_score >= 70:
                    imagen_success = True
                    model_used = "imagen4"
                    logger.info("Imagen 4 edit passed quality check.")
                else:
                    logger.warning(
                        f"Imagen 4 quality check failed (score={quality_score} < 70). "
                        f"Falling back to Flux Kontext Pro."
                    )
            else:
                logger.warning(f"Quality check returned error: {quality_result['error']}. Falling back.")
        else:
            logger.warning("Imagen 4 returned no images. Falling back to Flux Kontext Pro.")

    except Exception as e:
        logger.error(f"Imagen 4 inpainting failed: {e}. Falling back to Flux Kontext Pro.")

    # Step 4: If quality < 70 or Imagen fails → fallback to Flux Kontext Pro
    if not imagen_success:
        try:
            logger.info("Attempting Flux Kontext Pro fallback (api.fluxapi.ai)...")
            image_b64 = _to_base64(image_path)

            flux_payload = {
                "model": "flux-kontext-pro",
                "input_image": image_b64,
                "prompt": sculpt_prompt,
                "enableTranslation": True,
            }

            flux_headers = {
                "Authorization": f"Bearer {FLUXAI_API_KEY}",
                "Content-Type": "application/json",
            }

            flux_response = requests.post(
                "https://api.fluxapi.ai/v1/images/generations",
                json=flux_payload,
                headers=flux_headers,
                timeout=60,
            )
            flux_response.raise_for_status()
            flux_data = flux_response.json()

            # Extract output image
            output_image_b64 = flux_data.get("output_image", "")
            if output_image_b64:
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(output_image_b64))

                model_used = "flux-kontext"
                credits_used = flux_data.get("credits_used", 5)
                logger.info(
                    f"Flux Kontext Pro edit saved to {output_path}. "
                    f"Credits consumed: {credits_used}"
                )

                # Run quality check on Flux output too
                quality_result = check_edit_quality.invoke(
                    {"original_path": image_path, "edited_path": output_path}
                )
                if "error" not in quality_result:
                    quality_score = quality_result.get("quality_score", 0)
                else:
                    quality_score = -1  # Could not assess quality
            else:
                raise ValueError("Flux Kontext Pro returned empty output_image")

        except Exception as e:
            # Both models failed → return error with original image path
            logger.error(f"Flux Kontext Pro fallback also failed: {e}")
            return {
                "error": f"Both Imagen 4 and Flux Kontext Pro failed. Last error: {str(e)}",
                "original_path": image_path,
                "tool": "edit_image",
            }

    # Step 5: Return success result
    logger.info(
        f"Image edit complete — model_used={model_used}, "
        f"quality_score={quality_score}, output={output_path}"
    )
    return {
        "output_path": output_path,
        "model_used": model_used,
        "quality_score": quality_score,
        "prompt_used": sculpt_prompt,
    }


def _detect_language(text: str) -> str:
    """Detect the language of the input text using Gemini."""
    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Identify the language of this text. Return ONLY the language name (e.g. "English", "Bahasa Melayu", "Mandarin", "Tamil", "Cantonese").
                        Text: {text}""",
        )
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Language detection failed, defaulting to English: {e}")
        return "English"


@tool
def rewrite_text(
    text: str,
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    feedback: str = "",
) -> dict:
    """Rewrite ad text to fix compliance violations while preserving brand voice, language, and length.

    Args:
        text: Original ad text to rewrite.
        violations: List of compliance violation descriptions to fix.
        market: Target market (e.g. "malaysia", "singapore").
        platform: Target platform (e.g. "tiktok", "meta").
        ethnicity: Target ethnicity (e.g. "malay", "chinese", "indian").
        age_group: Target age group (e.g. "gen_z", "millennial").
        feedback: Optional reviewer feedback for the rewrite.

    Returns:
        Dict with "rewritten_text" and "changes_made" on success,
        or original text with error description on failure.
    """
    from agent.prompts import TEXT_REWRITE_PROMPT

    # Detect language of input text
    detected_language = _detect_language(text)
    logger.info(f"Detected language: {detected_language}")

    # Calculate length constraints (20% variance)
    original_length = len(text)
    min_length = int(original_length * 0.8)
    max_length = int(original_length * 1.2)

    # Build prompt from template
    violations_text = "\n".join(f"- {v}" for v in violations)
    feedback_section = f"REVIEWER FEEDBACK:\n{feedback}" if feedback else ""

    prompt = TEXT_REWRITE_PROMPT.format(
        text=text,
        violations_text=violations_text,
        market=market.title(),
        platform=platform.title(),
        ethnicity=ethnicity.title(),
        age_group=age_group,
        feedback_section=feedback_section,
        detected_language=detected_language,
        original_length=original_length,
        min_length=min_length,
        max_length=max_length,
    )

    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)

        # Normalize key: accept both "changes" and "changes_made"
        if "changes" in result and "changes_made" not in result:
            result["changes_made"] = result.pop("changes")

        rewritten = result.get("rewritten_text", "")

        # Validate output length (20% variance enforcement)
        if rewritten and (len(rewritten) < min_length or len(rewritten) > max_length):
            logger.warning(
                f"Rewritten text length {len(rewritten)} outside bounds "
                f"[{min_length}, {max_length}]. Requesting adjustment."
            )
            # Retry with stricter instruction
            retry_prompt = (
                f"The following rewritten text is {len(rewritten)} characters but must be "
                f"between {min_length} and {max_length} characters. "
                f"Adjust it to fit within the length constraint while keeping all fixes.\n\n"
                f"Text: {rewritten}\n\n"
                f"Return ONLY a JSON object: "
                f'{{"rewritten_text": "adjusted text", "changes_made": {json.dumps(result.get("changes_made", []))}}}'
            )
            retry_response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=retry_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            retry_result = json.loads(retry_response.text)
            if "changes" in retry_result and "changes_made" not in retry_result:
                retry_result["changes_made"] = retry_result.pop("changes")
            adjusted = retry_result.get("rewritten_text", "")
            if adjusted and min_length <= len(adjusted) <= max_length:
                return {
                    "rewritten_text": adjusted,
                    "changes_made": retry_result.get("changes_made", result.get("changes_made", [])),
                }
            # If retry still fails bounds, return what we have with a warning
            logger.warning("Length adjustment retry still out of bounds, returning best effort.")

        return {
            "rewritten_text": rewritten,
            "changes_made": result.get("changes_made", []),
        }

    except Exception as e:
        logger.error(f"Text rewrite failed: {e}")
        return {
            "rewritten_text": text,
            "changes_made": [f"Error: Gemini call failed — {str(e)}. Original text returned unchanged."],
        }


# ── Audio Remediation ─────────────────────────────────────────────────────────


def _get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file in seconds using FFmpeg/FFprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get duration for {audio_path}: {e}")
        return 0.0


def _extract_audio_segment(audio_path: str, start: float, end: float, output_path: str) -> bool:
    """Extract a segment from an audio file using FFmpeg.

    Args:
        audio_path: Source audio file path.
        start: Start time in seconds.
        end: End time in seconds.
        output_path: Where to save the extracted segment.

    Returns:
        True if extraction succeeded, False otherwise.
    """
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", audio_path,
        "-t", str(duration),
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"FFmpeg segment extraction failed: {result.stderr.decode()}")
            return False
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"FFmpeg segment extraction error: {e}")
        return False


def _trim_or_pad_audio(audio_path: str, target_duration: float, output_path: str) -> bool:
    """Trim or pad an audio file to match target duration within ±0.2s tolerance.

    If the audio is longer than target, it is trimmed.
    If it is shorter, silence is padded at the end.

    Args:
        audio_path: Input audio file path.
        target_duration: Desired duration in seconds.
        output_path: Where to save the adjusted audio.

    Returns:
        True if adjustment succeeded, False otherwise.
    """
    current_duration = _get_audio_duration(audio_path)
    if current_duration == 0.0:
        logger.warning("Cannot determine current audio duration, skipping trim/pad.")
        # Copy as-is
        cmd = ["ffmpeg", "-y", "-i", audio_path, "-c", "copy", output_path]
        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path)

    diff = current_duration - target_duration

    # Already within tolerance
    if abs(diff) <= 0.2:
        cmd = ["ffmpeg", "-y", "-i", audio_path, "-c", "copy", output_path]
        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path)

    if diff > 0:
        # Trim: audio is too long
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-t", str(target_duration),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            output_path,
        ]
    else:
        # Pad: audio is too short — add silence at end
        pad_duration = target_duration - current_duration
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-af", f"apad=pad_dur={pad_duration}",
            "-t", str(target_duration),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            output_path,
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"FFmpeg trim/pad failed: {result.stderr.decode()}")
            return False
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"FFmpeg trim/pad error: {e}")
        return False


@tool
def remix_audio(
    audio_path: str,
    violations: list,
    replacement_text: str,
    market: str,
    ethnicity: str,
    gender: str = "female",
    is_video_context: bool = False,
) -> dict:
    """Regenerate a non-compliant audio segment with a culturally appropriate voice.

    Extracts the violating segment, selects an appropriate ElevenLabs voice based on
    market/ethnicity/gender, generates replacement TTS audio, and matches the original
    segment duration. Supports lip-sync dubbing for video contexts.

    Args:
        audio_path: Path to the source audio file.
        violations: List of violation dicts with start/end timestamps and descriptions.
        replacement_text: Compliant text to speak in place of the violating segment.
        market: Target market (e.g. "malaysia", "singapore").
        ethnicity: Target ethnicity (e.g. "malay", "chinese", "indian").
        gender: Voice gender preference ("male" or "female"). Defaults to "female".
        is_video_context: If True, use ElevenLabs dubbing API with lip-sync.

    Returns:
        Dict with output_path, voice_id, and duration_match on success,
        or error dict with original audio path preserved on failure.
    """
    os.makedirs("assets/edits", exist_ok=True)

    # Parse timestamps from violations
    start_time = None
    end_time = None
    for v in violations:
        if isinstance(v, dict):
            if "start" in v:
                start_time = float(v["start"])
            elif "start_seconds" in v:
                start_time = float(v["start_seconds"])
            if "end" in v:
                end_time = float(v["end"])
            elif "end_seconds" in v:
                end_time = float(v["end_seconds"])
            if start_time is not None and end_time is not None:
                break

    if start_time is None or end_time is None:
        logger.error("Could not extract start/end timestamps from violations.")
        return {
            "error": "Missing start/end timestamps in violations.",
            "original_path": audio_path,
            "tool": "remix_audio",
        }

    segment_duration = end_time - start_time
    if segment_duration <= 0:
        logger.error(f"Invalid segment duration: {segment_duration}s")
        return {
            "error": f"Invalid segment duration ({start_time}s to {end_time}s).",
            "original_path": audio_path,
            "tool": "remix_audio",
        }

    # Step 1: Extract violating segment via FFmpeg
    segment_path = f"assets/edits/segment_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
    if not _extract_audio_segment(audio_path, start_time, end_time, segment_path):
        logger.error("Failed to extract audio segment.")
        return {
            "error": "FFmpeg extraction failed.",
            "original_path": audio_path,
            "tool": "remix_audio",
        }
    logger.info(f"Extracted segment ({start_time}s–{end_time}s) → {segment_path}")

    # Step 2: Select voice ID from VOICE_CONFIG
    voice_key = (market.lower(), ethnicity.lower(), gender.lower())
    voice_config = VOICE_CONFIG.get(voice_key, DEFAULT_VOICE)
    voice_id = voice_config["voice_id"]
    logger.info(f"Selected voice: {voice_key} → {voice_id} (fallback={voice_key not in VOICE_CONFIG})")

    # Step 3: Generate replacement audio via ElevenLabs TTS
    output_filename = f"remix_audio_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
    output_path = f"assets/edits/{output_filename}"

    try:
        if elevenlabs is None:
            raise RuntimeError("ElevenLabs client not available (elevenlabs package not installed).")

        if is_video_context:
            # Step 5: Use ElevenLabs dubbing API with lip-sync for video context
            logger.info("Video context detected — using ElevenLabs dubbing API with lip-sync.")
            try:
                dub_result = elevenlabs.dubbing.create(
                    source_url=audio_path,
                    target_lang=voice_config.get("lang", "en"),
                    voice_id=voice_id,
                )
                dubbing_id = dub_result.dubbing_id
                logger.info(f"Dubbing job created: {dubbing_id}")

                # Download dubbed audio
                dubbed_audio = elevenlabs.dubbing.get_dubbed_file(dubbing_id)
                with open(output_path, "wb") as f:
                    if hasattr(dubbed_audio, "read"):
                        f.write(dubbed_audio.read())
                    elif isinstance(dubbed_audio, bytes):
                        f.write(dubbed_audio)
                    else:
                        # Iterator/generator of bytes
                        for chunk in dubbed_audio:
                            f.write(chunk)
                logger.info(f"Dubbed audio saved to {output_path}")
            except Exception as dub_err:
                logger.warning(f"Dubbing API failed, falling back to standard TTS: {dub_err}")
                # Fallback to standard TTS (skip lip-sync)
                audio_response = elevenlabs.text_to_speech.convert(
                    voice_id=voice_id,
                    text=replacement_text,
                    model_id="eleven_v3",
                    voice_settings={
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                )
                with open(output_path, "wb") as f:
                    if hasattr(audio_response, "content"):
                        f.write(audio_response.content)
                    elif hasattr(audio_response, "read"):
                        f.write(audio_response.read())
                    else:
                        for chunk in audio_response:
                            f.write(chunk)
        else:
            # Standard TTS (non-video context)
            audio_response = elevenlabs.text_to_speech.convert(
                voice_id=voice_id,
                text=replacement_text,
                model_id="eleven_v3",
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            )
            with open(output_path, "wb") as f:
                if hasattr(audio_response, "content"):
                    f.write(audio_response.content)
                elif hasattr(audio_response, "read"):
                    f.write(audio_response.read())
                else:
                    for chunk in audio_response:
                        f.write(chunk)
            logger.info(f"TTS audio generated → {output_path}")

    except Exception as e:
        logger.error(f"ElevenLabs TTS generation failed: {e}")
        # Clean up segment file
        if os.path.exists(segment_path):
            os.remove(segment_path)
        return {
            "error": f"ElevenLabs TTS failed: {str(e)}",
            "original_path": audio_path,
            "tool": "remix_audio",
        }

    # Step 4: Trim or pad output to match original segment duration (±0.2s tolerance)
    adjusted_path = f"assets/edits/adjusted_{output_filename}"
    duration_match = _trim_or_pad_audio(output_path, segment_duration, adjusted_path)

    if duration_match and os.path.exists(adjusted_path):
        # Replace output with adjusted version
        os.replace(adjusted_path, output_path)
        final_duration = _get_audio_duration(output_path)
        duration_within_tolerance = abs(final_duration - segment_duration) <= 0.2
        logger.info(
            f"Duration matching: target={segment_duration:.2f}s, "
            f"actual={final_duration:.2f}s, within_tolerance={duration_within_tolerance}"
        )
    else:
        # Trim/pad failed — use raw TTS output and note mismatch
        duration_within_tolerance = False
        logger.warning("Duration trim/pad failed, using raw TTS output.")

    # Clean up temporary segment file
    if os.path.exists(segment_path):
        os.remove(segment_path)

    logger.info(
        f"Audio remix complete — voice_id={voice_id}, "
        f"duration_match={duration_within_tolerance}, output={output_path}"
    )
    return {
        "output_path": output_path,
        "voice_id": voice_id,
        "duration_match": duration_within_tolerance,
    }


@tool
def check_edit_quality(original_path, edited_path):
    """Compare original vs edited image — check if edit looks natural."""
    import mimetypes

    orig_b64 = _to_base64(original_path)
    edit_b64 = _to_base64(edited_path)
    orig_mime = mimetypes.guess_type(original_path)[0] or "image/png"
    edit_mime = mimetypes.guess_type(edited_path)[0] or "image/png"

    prompt = """Compare ORIGINAL and EDITED advertisement images.

                Evaluate the EDITED image:
                1. Visual integrity (no artifacts, warping, inconsistent lighting)
                2. Brand preservation (logo, colors, product unchanged)
                3. Edit naturalness (fix blends seamlessly)
                4. Advertising appeal (still sells the product)

                Return JSON:
                {"quality_score": 0-100, "pass": true/false, "issues": ["issue 1"], "explanation": "short reason"}

                Pass if quality_score >= 70 and no major artifacts."""

    try:
        response = gemini.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(parts=[
                types.Part.from_text(text="ORIGINAL:"),
                types.Part.from_bytes(data=base64.b64decode(orig_b64), mime_type=orig_mime),
                types.Part.from_text(text="EDITED:"),
                types.Part.from_bytes(data=base64.b64decode(edit_b64), mime_type=edit_mime),
                types.Part.from_text(text=prompt),
            ])],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Quality check failed: {e}")
        return {"error": str(e)}


# ── Video Composition Helpers ─────────────────────────────────────────────────


def _get_video_duration(file_path: str) -> float:
    """Get the duration of a media file using FFprobe.

    Args:
        file_path: Path to the media file.

    Returns:
        Duration in seconds, or 0.0 if probe fails.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning(f"Failed to get media duration for {file_path}: {e}")
    return 0.0


def _extract_video_segment(
    video_path: str, start: float, end: float, output_path: str
) -> bool:
    """Extract a video segment from start to end seconds using FFmpeg.

    Uses -c copy for speed; falls back to re-encoding if copy fails.

    Args:
        video_path: Source video file path.
        start: Start time in seconds.
        end: End time in seconds.
        output_path: Path for the extracted segment file.

    Returns:
        True if extraction was successful, False otherwise.
    """
    duration = end - start
    if duration <= 0:
        return False

    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            # Fallback: re-encode if -c copy fails (keyframe issues)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                logger.warning(f"Segment extraction failed: {result.stderr[:300]}")
                return False

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"Segment extraction error: {e}")
        return False


def _collect_edit_points(visual_edits: list[dict], audio_edits: list[dict]) -> list[float]:
    """Collect all unique edit boundary timestamps, sorted."""
    points = set()
    for edit in visual_edits:
        points.add(edit["start"])
        points.add(edit["end"])
    for edit in audio_edits:
        points.add(edit["start"])
        points.add(edit["end"])
    return sorted(points)


@tool
def compose_video(
    video_path: str,
    visual_edits: list[dict],
    audio_edits: list[dict],
) -> dict:
    """Compose a remediated video by splicing visual replacements and overlaying audio edits.

    Splits the original video at edit points, replaces visual segments with
    remediated clips where successful, overlays remediated audio at correct
    timestamps, and concatenates all segments preserving codec/resolution/fps.
    Handles partial remediation by keeping original content for failed segments.

    Args:
        video_path: Path to the original source video.
        visual_edits: List of visual edit dicts, each with keys:
            - start (float): Start timestamp in seconds.
            - end (float): End timestamp in seconds.
            - replacement_path (str): Path to the replacement video/image clip.
            - success (bool): Whether this remediation succeeded.
        audio_edits: List of audio edit dicts, each with keys:
            - start (float): Start timestamp in seconds.
            - end (float): End timestamp in seconds.
            - replacement_path (str): Path to the replacement audio file.
            - success (bool): Whether this remediation succeeded.

    Returns:
        Dict with output_path, segments_replaced, and warnings on success,
        or error dict with original video path preserved on failure.
    """
    os.makedirs("assets/edits", exist_ok=True)
    warnings: list[str] = []

    # Validate input video exists
    if not video_path or not os.path.exists(video_path):
        logger.error(f"Original video not found: {video_path}")
        return {
            "error": f"Original video not found: {video_path}",
            "original_path": video_path,
            "tool": "compose_video",
        }

    # Filter successful edits only
    successful_visual = [e for e in visual_edits if e.get("success")]
    successful_audio = [e for e in audio_edits if e.get("success")]
    failed_visual = [e for e in visual_edits if not e.get("success")]
    failed_audio = [e for e in audio_edits if not e.get("success")]

    # Track partial remediation warnings
    for fv in failed_visual:
        warnings.append(
            f"Visual segment {fv.get('start', '?')}s-{fv.get('end', '?')}s failed — keeping original"
        )
    for fa in failed_audio:
        warnings.append(
            f"Audio segment {fa.get('start', '?')}s-{fa.get('end', '?')}s failed — keeping original"
        )

    # If no remediations succeeded, return original video with warning
    if not successful_visual and not successful_audio:
        logger.warning("No remediations succeeded — returning original video.")
        warnings.append("No remediations succeeded; original video returned unchanged.")
        return {
            "output_path": video_path,
            "segments_replaced": 0,
            "warnings": warnings,
        }

    # Get original video duration
    original_duration = _get_video_duration(video_path)
    if original_duration <= 0:
        logger.error("Could not determine original video duration.")
        return {
            "error": "Could not determine original video duration",
            "original_path": video_path,
            "tool": "compose_video",
        }

    output_id = uuid.uuid4().hex[:12]
    output_filename = f"composed_{output_id}.mp4"
    output_path = f"assets/edits/{output_filename}"
    temp_dir = tempfile.mkdtemp(prefix="compose_video_")
    segments_replaced = 0

    try:
        # ── Step 1: Split original video into segments at edit points ─────────
        # Collect all visual edit boundaries to determine split points
        edit_points = [0.0]
        for ve in successful_visual:
            edit_points.append(ve["start"])
            edit_points.append(ve["end"])
        edit_points.append(original_duration)
        # Deduplicate and sort
        edit_points = sorted(set(edit_points))

        # Build a lookup of successful visual edits by (start, end)
        visual_lookup: dict[tuple[float, float], dict] = {}
        for ve in successful_visual:
            visual_lookup[(ve["start"], ve["end"])] = ve

        # ── Step 2: Build segment list — replace visual segments with remediated clips ──
        segment_files: list[str] = []

        for i in range(len(edit_points) - 1):
            seg_start = edit_points[i]
            seg_end = edit_points[i + 1]

            if seg_end <= seg_start:
                continue

            # Check if this segment matches a successful visual edit
            visual_edit = visual_lookup.get((seg_start, seg_end))

            if visual_edit and visual_edit.get("replacement_path"):
                replacement_path = visual_edit["replacement_path"]
                if os.path.exists(replacement_path):
                    segment_files.append(replacement_path)
                    segments_replaced += 1
                    logger.info(
                        f"Replacing visual segment {seg_start:.2f}s-{seg_end:.2f}s "
                        f"with {replacement_path}"
                    )
                else:
                    # Replacement file missing — fall back to original
                    logger.warning(
                        f"Replacement file not found: {replacement_path}. "
                        f"Keeping original for {seg_start:.2f}s-{seg_end:.2f}s"
                    )
                    warnings.append(
                        f"Replacement file missing for {seg_start:.2f}s-{seg_end:.2f}s — keeping original"
                    )
                    seg_output = os.path.join(temp_dir, f"seg_{i:03d}.mp4")
                    if _extract_video_segment(video_path, seg_start, seg_end, seg_output):
                        segment_files.append(seg_output)
                    else:
                        warnings.append(f"Failed to extract fallback segment {seg_start:.2f}s-{seg_end:.2f}s")
            else:
                # No visual edit for this range — extract original segment
                seg_output = os.path.join(temp_dir, f"seg_{i:03d}.mp4")
                if _extract_video_segment(video_path, seg_start, seg_end, seg_output):
                    segment_files.append(seg_output)
                else:
                    logger.warning(f"Failed to extract segment {seg_start:.2f}s-{seg_end:.2f}s")
                    warnings.append(f"Failed to extract segment {seg_start:.2f}s-{seg_end:.2f}s")

        if not segment_files:
            logger.error("No video segments could be assembled.")
            return {
                "error": "No video segments could be assembled",
                "original_path": video_path,
                "tool": "compose_video",
            }

        # ── Step 4: Concatenate all segments preserving codec/resolution/fps ──
        if len(segment_files) == 1:
            concatenated_path = segment_files[0]
        else:
            # Use FFmpeg concat demuxer
            concat_list_path = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list_path, "w") as f:
                for seg_file in segment_files:
                    safe_path = seg_file.replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")

            concatenated_path = os.path.join(temp_dir, f"concatenated_{output_id}.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                "-movflags", "+faststart",
                concatenated_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                # Fallback: re-encode if -c copy fails (mixed encodings)
                logger.warning("Concat with -c copy failed, retrying with re-encoding.")
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    concatenated_path,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    logger.error(f"Video concatenation failed: {result.stderr[:500]}")
                    return {
                        "error": f"FFmpeg concatenation failed: {result.stderr[:200]}",
                        "original_path": video_path,
                        "tool": "compose_video",
                    }

            if not os.path.exists(concatenated_path) or os.path.getsize(concatenated_path) == 0:
                logger.error("Concatenated video file is empty or missing.")
                return {
                    "error": "Concatenated video file is empty or missing",
                    "original_path": video_path,
                    "tool": "compose_video",
                }

        # ── Step 3: Overlay remediated audio at correct timestamps ─────────────
        if successful_audio:
            # Build FFmpeg filter_complex for audio overlay
            input_args = ["-y", "-i", concatenated_path]

            for ae in successful_audio:
                replacement_path = ae.get("replacement_path", "")
                if replacement_path and os.path.exists(replacement_path):
                    input_args.extend(["-i", replacement_path])
                else:
                    warnings.append(
                        f"Audio replacement file missing for {ae.get('start', '?')}s-{ae.get('end', '?')}s"
                    )

            # Count valid audio inputs
            valid_audio_inputs = []
            audio_input_idx = 1  # input 0 is the concatenated video
            for ae in successful_audio:
                replacement_path = ae.get("replacement_path", "")
                if replacement_path and os.path.exists(replacement_path):
                    valid_audio_inputs.append((audio_input_idx, ae))
                    audio_input_idx += 1

            if valid_audio_inputs:
                # Build filter_complex to overlay audio at timestamps
                filter_parts = []
                overlay_labels = []

                for idx, (input_idx, ae) in enumerate(valid_audio_inputs):
                    start_ms = int(ae["start"] * 1000)
                    # Delay the audio replacement to the correct timestamp
                    filter_parts.append(
                        f"[{input_idx}:a]adelay={start_ms}|{start_ms},apad[ao{idx}]"
                    )
                    overlay_labels.append(f"[ao{idx}]")
                    segments_replaced += 1

                # Mix original video audio with overlaid replacement audio
                all_inputs = "[0:a]" + "".join(overlay_labels)
                num_inputs = 1 + len(overlay_labels)
                filter_parts.append(
                    f"{all_inputs}amix=inputs={num_inputs}:duration=first:dropout_transition=0[aout]"
                )

                filter_complex = ";".join(filter_parts)

                final_cmd = ["ffmpeg"] + input_args + [
                    "-filter_complex", filter_complex,
                    "-map", "0:v",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    output_path,
                ]

                result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    # Fallback: try re-encoding video as well
                    logger.warning("Audio overlay with -c:v copy failed, retrying with re-encoding.")
                    final_cmd = ["ffmpeg"] + input_args + [
                        "-filter_complex", filter_complex,
                        "-map", "0:v",
                        "-map", "[aout]",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart",
                        output_path,
                    ]
                    result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=300)

                    if result.returncode != 0:
                        logger.error(f"Audio overlay failed: {result.stderr[:500]}")
                        # Fall through: use concatenated video without audio overlay
                        warnings.append("Audio overlay failed — using video without audio edits")
                        import shutil
                        shutil.copy2(concatenated_path, output_path)
            else:
                # No valid audio files, just copy concatenated to output
                import shutil
                shutil.copy2(concatenated_path, output_path)
        else:
            # No audio edits — copy concatenated video to output path
            import shutil
            shutil.copy2(concatenated_path, output_path)

        # Verify output exists
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error("Final composed video file is empty or missing.")
            return {
                "error": "Final composed video is empty or missing",
                "original_path": video_path,
                "tool": "compose_video",
            }

        logger.info(
            f"Video composition complete — output={output_path}, "
            f"segments_replaced={segments_replaced}, warnings={len(warnings)}"
        )
        return {
            "output_path": output_path,
            "segments_replaced": segments_replaced,
            "warnings": warnings,
        }

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg operation timed out during video composition.")
        return {
            "error": "FFmpeg timed out during video composition",
            "original_path": video_path,
            "tool": "compose_video",
        }
    except FileNotFoundError:
        logger.error("FFmpeg not found. Ensure FFmpeg is installed and on PATH.")
        return {
            "error": "FFmpeg not found — ensure FFmpeg is installed and on PATH",
            "original_path": video_path,
            "tool": "compose_video",
        }
    except Exception as e:
        logger.error(f"Video composition failed: {e}")
        return {
            "error": f"Video composition failed: {str(e)}",
            "original_path": video_path,
            "tool": "compose_video",
        }
    finally:
        # Clean up temp directory
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
