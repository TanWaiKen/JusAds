import os
import json
import base64
import logging
import subprocess
import tempfile
import time
import uuid
import numpy as np
from PIL import Image
from google.genai import types
from shared.clients import gemini, elevenlabs
from shared.config import MODEL_TEXT
from jusads_compliance.prompts import SCULPT_PROMPT_TEMPLATE
from config import get_voice
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def _to_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _make_binary_mask(segmented_path: str, original_path: str) -> str:
    """Compare segmented overlay vs original to produce a binary mask.

    The segmented image is the original with a colored overlay on violation regions.
    We diff the two to find where the overlay is â†’ that becomes the mask.

    White = edit region (where overlay was painted), Black = keep unchanged.
    """
    orig = np.array(Image.open(original_path).convert("RGB"))
    seg = np.array(Image.open(segmented_path).convert("RGB"))

    # Resize if dimensions don't match
    if orig.shape != seg.shape:
        orig = np.array(Image.open(original_path).convert("RGB").resize(
            (seg.shape[1], seg.shape[0]), Image.LANCZOS
        ))

    # Compute per-pixel difference
    diff = np.abs(seg.astype(int) - orig.astype(int)).sum(axis=2)
    # Threshold: pixels with significant color change = overlay region
    mask = (diff > 50).astype(np.uint8) * 255

    mask_img = Image.fromarray(mask, mode="L")
    mask_path = segmented_path.replace("segmented_", "mask_")
    if mask_path == segmented_path:
        mask_path = segmented_path.rsplit(".", 1)[0] + "_mask.png"
    mask_img.save(mask_path)
    return mask_path



# â”€â”€ Platform style mappings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_PLATFORM_STYLES = {
    "general": {
        "description": "General advertising: professional, appealing, brand-appropriate",
        "keywords": ["professional", "appealing"],
    },
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



def _build_sculpt_prompt(
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    localization_plan: str = "",
) -> str:
    """Generate a SCULPT framework image editing prompt via Gemini.

    Args:
        violations: List of compliance violation descriptions to fix.
        market: Target market.
        platform: Advertising platform.
        ethnicity: Target ethnicity for cultural context.
        age_group: Target age group.
        localization_plan: Localization guidance from the compliance result (e.g.
            "do not show face, show product only, cover exposed body").

    Returns:
        A structured SCULPT prompt string for image editing.
    """
    platform_key = platform.lower().strip()
    style_info = _PLATFORM_STYLES.get(platform_key, _PLATFORM_STYLES["general"])

    platform_style = style_info["description"]
    platform_keywords = style_info["keywords"]

    violations_text = json.dumps(violations, indent=2)

    prompt_input = SCULPT_PROMPT_TEMPLATE.format(
        violations=violations_text,
        market=market,
        platform=platform,
        ethnicity=ethnicity,
        age_group=age_group,
        platform_style=platform_style,
        platform_keywords=platform_keywords,
        localization_plan=localization_plan or "No additional localization guidance provided.",
    )

    response = gemini.models.generate_content(
        model=MODEL_TEXT,
        contents=prompt_input,
    )
    sculpt_prompt = response.text.strip()
    logger.info(f"SCULPT prompt generated for {platform}/{market} ({len(sculpt_prompt)} chars)")
    return sculpt_prompt


# â”€â”€ Edit mode decision â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_EDIT_MODES = {
    "EDIT_MODE_INPAINT_REMOVAL": "Remove the non-compliant content from the masked region entirely.",
    "EDIT_MODE_INPAINT_INSERTION": "Replace the masked region with new compliant content.",
    "EDIT_MODE_BGSWAP": "Replace the background while keeping the subject intact.",
    "EDIT_MODE_OUTPAINT": "Extend the image beyond its original boundaries.",
}


def _decide_edit_mode(sculpt_prompt: str, feedback: str = "") -> tuple[str, str]:
    """Read the SCULPT prompt and decide the best Imagen edit mode + inpainting prompt.

    SCULPT already contains violations, platform, audience and style context,
    so we feed it directly â€” no need to rebuild context here.

    Returns:
        (edit_mode, inpaint_prompt)
    """
    modes_desc = "\n".join(f"- {k}: {v}" for k, v in _EDIT_MODES.items())
    feedback_line = f"\nReviewer feedback: {feedback}" if feedback else ""

    prompt = f"""You are an image editing specialist. Read the SCULPT editing brief and decide:
1. Which Imagen edit mode to use.
2. A concise inpainting prompt (max 60 words) based on the brief.

SCULPT BRIEF:
{sculpt_prompt}
{feedback_line}

AVAILABLE EDIT MODES:
{modes_desc}

RULES for the inpainting prompt:
- REMOVAL: describe the natural fill (e.g. "smooth background matching surroundings"), or use ""
- INSERTION/BGSWAP/OUTPAINT: describe what should appear (positive language only)

Return ONLY a JSON object:
{{"edit_mode": "EDIT_MODE_INPAINT_INSERTION", "inpaint_prompt": "..."}}"""

    response = gemini.models.generate_content(
        model=MODEL_TEXT,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    result = json.loads(response.text)
    edit_mode = result.get("edit_mode", "EDIT_MODE_INPAINT_INSERTION")
    inpaint_prompt = result.get("inpaint_prompt", "")

    if edit_mode not in _EDIT_MODES:
        logger.warning(f"Unknown edit mode '{edit_mode}' â€” defaulting to INPAINT_INSERTION")
        edit_mode = "EDIT_MODE_INPAINT_INSERTION"

    logger.info(f"Decided â€” mode: {edit_mode} | prompt: {inpaint_prompt}")
    return edit_mode, inpaint_prompt


@tool
def edit_image(
    project_id: str,
    task_id: str,
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    localization_plan: str = "",
    feedback: str = "",
) -> dict:
    """Fix compliance violations in an image using a Gemini-directed Imagen editing agent.

    Flow:
      0. Fetch task context from Supabase (extracts localization_plan from result_json if not provided)
      1. Convert segmented overlay to binary mask (white = edit region, black = keep)
      2. Build SCULPT prompt (violations + localization_plan + platform + audience context)
      3. Gemini reads SCULPT to decide edit_mode + inpainting prompt
      4. Loop: imagen-3.0-capability-002 with user-provided mask -> quality check -> refine if < 70 (max 3 attempts)
      5. Upload result to S3
      6. Persist s3_remix_key to Supabase

    Args:
        project_id: The project UUID.
        task_id: The task UUID.
        image_path: Path to the original source image.
        segmented_path: Path to the segmentation overlay image (CLIPSeg output) â€” used as the edit mask.
        violations: List of compliance violation descriptions.
        market: Target market.
        platform: Target platform.
        ethnicity: Target ethnicity.
        age_group: Target age group.
        localization_plan: Localization guidance from compliance result. Auto-extracted from
            task result_json if not provided.
        feedback: Optional reviewer feedback.

    Returns:
        Dict with output_path, s3_url, model_used, edit_mode, quality_score, attempts, prompt_used.
    """
    from shared.supabase_client import get_task, update_check
    from shared.s3_client import upload_file_public, build_s3_key
    import tempfile
    import urllib.request

    # Step 0: Fetch task context from Supabase
    task = get_task(project_id, task_id)
    if not task:
        raise RuntimeError(f"Task {task_id} not found in project {project_id}")
    compliance = task.get("compliance", {}) or {}
    user_id = project_id

    # Extract localization_plan from compliance result_json if not passed explicitly
    if not localization_plan:
        result_json = compliance.get("result_json") or {}
        localization_plan = result_json.get("localization_plan", "")

    # Auto-resolve image and segmented mask from S3
    s3_upload_url = compliance.get("s3_upload_key", "")
    if not s3_upload_url:
        raise FileNotFoundError("s3_upload_key not found in task compliance data")
    logger.info(f"Downloading original image from S3: {s3_upload_url}")
    image_path = os.path.join(tempfile.gettempdir(), f"original_{task_id}.png")
    urllib.request.urlretrieve(s3_upload_url, image_path)

    s3_segmented_url = compliance.get("s3_segmented_key", "")
    if not s3_segmented_url:
        raise FileNotFoundError("s3_segmented_key not found in task compliance data")
    logger.info(f"Downloading segmented mask from S3: {s3_segmented_url}")
    segmented_path = os.path.join(tempfile.gettempdir(), f"segmented_{task_id}.png")
    urllib.request.urlretrieve(s3_segmented_url, segmented_path)

    output_filename = f"edited_{int(time.time())}_{os.path.basename(image_path)}"
    output_path = os.path.join(tempfile.gettempdir(), output_filename)

    logger.info(f"Task context - task_id={task_id}, localization_plan: {localization_plan[:80] if localization_plan else 'none'}")

    # Step 1: Convert segmented overlay -> binary mask (compare with original)
    mask_path = _make_binary_mask(segmented_path, image_path)
    logger.info(f"Binary mask created: {mask_path}")

    # Step 2: SCULPT prompt (violations + localization guidance)
    sculpt_prompt = _build_sculpt_prompt(
        violations, market, platform, ethnicity, age_group, localization_plan
    )
    if feedback:
        sculpt_prompt += f" Additional guidance: {feedback}"

    # Step 3: Gemini reads SCULPT -> edit mode + inpainting prompt
    edit_mode, inpaint_prompt = _decide_edit_mode(sculpt_prompt, feedback)

    image_b64_bytes = base64.b64decode(_to_base64(image_path))
    mask_b64_bytes = base64.b64decode(_to_base64(mask_path))

    # Step 4: Edit loop - max 3 attempts
    MAX_ATTEMPTS = 3
    quality_score = 0
    attempt = 0
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(f"Attempt {attempt}/{MAX_ATTEMPTS} - mode={edit_mode}")
        try:
            response = gemini.models.edit_image(
                model="imagen-3.0-capability-002",
                prompt=inpaint_prompt,
                reference_images=[
                    types.RawReferenceImage(
                        reference_image=types.Image(image_bytes=image_b64_bytes),
                        reference_id=1,
                    ),
                    types.MaskReferenceImage(
                        reference_image=types.Image(image_bytes=mask_b64_bytes),
                        reference_id=2,
                        config=types.MaskReferenceConfig(
                            mask_mode="MASK_MODE_USER_PROVIDED",
                        ),
                    ),
                ],
                config=types.EditImageConfig(
                    edit_mode=edit_mode,
                    number_of_images=1,
                    safety_filter_level="BLOCK_SOME",
                    person_generation="ALLOW_ALL",
                ),
            )

            if not response.generated_images:
                raise ValueError("Imagen returned no images")

            with open(output_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)

            quality_result = check_edit_quality.invoke(
                {"original_path": image_path, "edited_path": output_path}
            )
            quality_score = quality_result.get("quality_score", 0) if "error" not in quality_result else 0
            logger.info(f"Quality: {quality_score}/100 (attempt {attempt})")

            if quality_score >= 70:
                logger.info(f"Quality passed on attempt {attempt}")
                break

            if attempt < MAX_ATTEMPTS:
                reason = quality_result.get("feedback", "Quality insufficient")
                refine = gemini.models.generate_content(
                    model=MODEL_TEXT,
                    contents=(
                        f"Image edit scored {quality_score}/100. Reason: {reason}\n"
                        f"Rewrite this Imagen inpainting prompt to improve it (max 60 words):\n{inpaint_prompt}"
                    ),
                )
                inpaint_prompt = refine.text.strip()
                logger.info(f"Refined prompt: {inpaint_prompt}")

        except Exception as e:
            last_error = str(e)
            logger.error(f"Attempt {attempt} failed: {e}")

    if quality_score < 70:
        return {
            "error": f"All {MAX_ATTEMPTS} attempts failed. Last error: {last_error}",
            "original_path": image_path,
            "tool": "edit_image",
        }

    # Step 5: Upload to S3
    s3_url = None
    s3_remix_key = None
    try:
        s3_remix_key = build_s3_key(
            asset_type="remixed",
            username=user_id,
            project_id=project_id,
            check_id=task_id,
            filename=output_filename,
        )
        s3_url = upload_file_public(output_path, s3_remix_key)
        logger.info(f"Uploaded to S3: {s3_url}")
    except Exception as e:
        logger.warning(f"S3 upload failed (saved locally): {e}")

    # Step 6: Persist to Supabase
    if s3_remix_key:
        try:
            update_check(task_id, status="remediated", s3_remix_key=s3_remix_key)
            logger.info(f"Updated task {task_id} -> remediated")
        except Exception as e:
            logger.warning(f"Supabase update failed: {e}")

    logger.info(f"edit_image done - mode={edit_mode}, quality={quality_score}, attempts={attempt}")
    return {
        "output_path": output_path,
        "s3_url": s3_url,
        "s3_remix_key": s3_remix_key,
        "model_used": "imagen-3.0-capability-002",
        "edit_mode": edit_mode,
        "quality_score": quality_score,
        "attempts": attempt,
        "prompt_used": sculpt_prompt,
    }

@tool
def generate_image(
    product: str,
    ad_concept: str,
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    guidance: str = "",
) -> dict:
    """Generate a brand new compliant ad image when the original is too non-compliant to edit.

    Uses Gemini to craft a culturally appropriate prompt, then Imagen 4 to generate
    the image. Falls back to Flux Kontext Pro if Imagen fails.

    Args:
        product: The product being advertised.
        ad_concept: The original ad concept/message to preserve.
        violations: List of violations from the original that must be avoided.
        market: Target market (e.g. "malaysia").
        platform: Target platform (e.g. "tiktok", "meta").
        ethnicity: Target ethnicity for cultural context.
        age_group: Target age group.
        guidance: Additional guidance for the generation.

    Returns:
        Dict with output_path, prompt_used, model_used on success,
        or error dict on failure.
    """
    output_filename = f"generated_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="generated_")
    tmp.close()
    output_path = tmp.name

    # Step 1: Generate a culturally appropriate prompt via Gemini
    prompt_request = f"""Create an advertising image generation prompt for:

PRODUCT: {product}
AD CONCEPT: {ad_concept}
TARGET MARKET: {market}
TARGET AUDIENCE: {ethnicity}, {age_group}
PLATFORM: {platform}

VIOLATIONS TO AVOID (from the original non-compliant ad):
{json.dumps(violations, indent=2)}

ADDITIONAL GUIDANCE:
{guidance}

RULES:
- The image MUST be culturally appropriate for {market} ({ethnicity} audience)
- AVOID all violations listed above
- Preserve the ad concept but make it compliant
- For modest markets: show product on mannequins, flat-lay, or packaging â€” NOT on models in revealing clothing
- Professional advertising quality, high resolution
- Max 75 words for the prompt
- Positive description only (what TO show, not what to avoid)

Return ONLY the image generation prompt text."""

    try:
        prompt_response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt_request,
        )
        generation_prompt = prompt_response.text.strip()
        logger.info(f"[GenerateImage] Prompt: {generation_prompt[:100]}...")
    except Exception as e:
        logger.error(f"[GenerateImage] Prompt generation failed: {e}")
        return {"error": f"Prompt generation failed: {e}", "tool": "generate_image"}

    # Step 2: Generate with Imagen 4
    try:
        logger.info("[GenerateImage] Generating with Imagen 4...")
        response = gemini.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=generation_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )

        if response.generated_images and len(response.generated_images) > 0:
            result_image = response.generated_images[0]
            with open(output_path, "wb") as f:
                f.write(result_image.image.image_bytes)
            logger.info(f"[GenerateImage] Imagen 4 saved to {output_path}")

            return {
                "output_path": output_path,
                "prompt_used": generation_prompt,
                "model_used": "imagen-4.0-generate-001",
            }
        else:
            logger.warning("[GenerateImage] Imagen 4 returned no images.")
            return {"error": "Imagen 4 returned no images", "tool": "generate_image"}

    except Exception as e:
        logger.warning(f"[GenerateImage] Imagen 4 failed: {e}")
        return {"error": f"Imagen 4 generation failed: {e}", "tool": "generate_image"}


def _detect_language(text: str) -> str:
    """Detect the language of the input text using Gemini."""
    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
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
    from jusads_compliance.prompts import TEXT_REWRITE_PROMPT

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
            model=MODEL_TEXT,
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
                model=MODEL_TEXT,
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
            "changes_made": [f"Error: Gemini call failed â€” {str(e)}. Original text returned unchanged."],
        }


# â”€â”€ Audio Remediation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
    """Trim or pad an audio file to match target duration within Â±0.2s tolerance.

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
        # Pad: audio is too short â€” add silence at end
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
    os.makedirs(tempfile.gettempdir(), exist_ok=True)

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
    segment_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="segment_")
    segment_tmp.close()
    segment_path = segment_tmp.name
    if not _extract_audio_segment(audio_path, start_time, end_time, segment_path):
        logger.error("Failed to extract audio segment.")
        return {
            "error": "FFmpeg extraction failed.",
            "original_path": audio_path,
            "tool": "remix_audio",
        }
    logger.info(f"Extracted segment ({start_time}sâ€“{end_time}s) â†’ {segment_path}")

    # Step 2: Select voice ID from brand_voices DB
    voice_config = get_voice(market, ethnicity, gender)
    voice_id = voice_config["voice_id"]
    logger.info(f"Selected voice: ({market}, {ethnicity}, {gender}) â†’ {voice_id}")

    # Step 3: Generate replacement audio via ElevenLabs TTS
    output_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="remix_audio_")
    output_tmp.close()
    output_path = output_tmp.name

    try:
        if elevenlabs is None:
            raise RuntimeError("ElevenLabs client not available (elevenlabs package not installed).")

        if is_video_context:
            # Step 5: Use ElevenLabs dubbing API with lip-sync for video context
            logger.info("Video context detected â€” using ElevenLabs dubbing API with lip-sync.")
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
            logger.info(f"TTS audio generated â†’ {output_path}")

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

    # Step 4: Trim or pad output to match original segment duration (Â±0.2s tolerance)
    adjusted_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="adjusted_")
    adjusted_tmp.close()
    adjusted_path = adjusted_tmp.name
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
        # Trim/pad failed â€” use raw TTS output and note mismatch
        duration_within_tolerance = False
        logger.warning("Duration trim/pad failed, using raw TTS output.")

    # Clean up temporary segment file
    if os.path.exists(segment_path):
        os.remove(segment_path)

    logger.info(
        f"Audio remix complete â€” voice_id={voice_id}, "
        f"duration_match={duration_within_tolerance}, output={output_path}"
    )
    return {
        "output_path": output_path,
        "voice_id": voice_id,
        "duration_match": duration_within_tolerance,
    }


@tool
def check_edit_quality(original_path, edited_path):
    """Compare original vs edited image â€” check if edit looks natural."""
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


# â”€â”€ Lightweight Bias Check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def check_edit_bias(
    original_path: str, edited_path: str, violations: list[str]
) -> dict:
    """Lightweight, single-pass bias and hallucination check on an edited image.

    Uses Gemini Flash (NOT Pro) to flag only egregious issues.
    This is NOT a @tool â€” it's called directly from the remix route handler.

    Args:
        original_path: Path to the original image.
        edited_path: Path to the edited image.
        violations: List of violation strings from the compliance check.

    Returns:
        BiasCheckResult-shaped dict: {passed: bool, issues: list[str], confidence: float}
        On Gemini failure: fail-open (passed=True, empty issues, confidence=0.0).
    """
    import mimetypes

    prompt = f"""Compare the ORIGINAL and EDITED advertisement images.

Check the EDITED image ONLY for EGREGIOUS issues:
1. Racial or ethnic bias introduced by the edit
2. Hallucinated content (objects/people that shouldn't be there)
3. Inappropriate or offensive content added by the edit
4. Gender stereotyping significantly worse than the original

DO NOT flag:
- Minor stylistic differences
- Slight color shifts
- Minor composition changes
- Issues that existed in the original

ORIGINAL VIOLATIONS BEING FIXED: {json.dumps(violations)}

Return JSON: {{"passed": true/false, "issues": ["issue 1", ...], "confidence": 0.0-1.0}}
Return passed=true if no egregious bias or hallucination issues found."""

    try:
        orig_b64 = _to_base64(original_path)
        edit_b64 = _to_base64(edited_path)
        orig_mime = mimetypes.guess_type(original_path)[0] or "image/png"
        edit_mime = mimetypes.guess_type(edited_path)[0] or "image/png"

        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=[types.Content(parts=[
                types.Part.from_text(text="ORIGINAL:"),
                types.Part.from_bytes(data=base64.b64decode(orig_b64), mime_type=orig_mime),
                types.Part.from_text(text="EDITED:"),
                types.Part.from_bytes(data=base64.b64decode(edit_b64), mime_type=edit_mime),
                types.Part.from_text(text=prompt),
            ])],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)
        passed = result.get("passed", True)
        issues = result.get("issues", [])
        confidence = float(result.get("confidence", 0.8))

        logger.info(
            "[LightBiasCheck] passed=%s, issues=%d, confidence=%.2f",
            passed, len(issues), confidence,
        )
        return {"passed": passed, "issues": issues, "confidence": confidence}

    except Exception as e:
        # Fail-open: bias check failure should not block the edit result
        logger.warning("[LightBiasCheck] Gemini call failed â€” fail-open: %s", e)
        return {"passed": True, "issues": [], "confidence": 0.0}


# â”€â”€ Video Composition Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
    os.makedirs(tempfile.gettempdir(), exist_ok=True)
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
            f"Visual segment {fv.get('start', '?')}s-{fv.get('end', '?')}s failed â€” keeping original"
        )
    for fa in failed_audio:
        warnings.append(
            f"Audio segment {fa.get('start', '?')}s-{fa.get('end', '?')}s failed â€” keeping original"
        )

    # If no remediations succeeded, return original video with warning
    if not successful_visual and not successful_audio:
        logger.warning("No remediations succeeded â€” returning original video.")
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
    output_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4", prefix="composed_")
    output_tmp.close()
    output_path = output_tmp.name
    temp_dir = tempfile.mkdtemp(prefix="compose_video_")
    segments_replaced = 0

    try:
        # â”€â”€ Step 1: Split original video into segments at edit points â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ Step 2: Build segment list â€” replace visual segments with remediated clips â”€â”€
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
                    # Replacement file missing â€” fall back to original
                    logger.warning(
                        f"Replacement file not found: {replacement_path}. "
                        f"Keeping original for {seg_start:.2f}s-{seg_end:.2f}s"
                    )
                    warnings.append(
                        f"Replacement file missing for {seg_start:.2f}s-{seg_end:.2f}s â€” keeping original"
                    )
                    seg_output = os.path.join(temp_dir, f"seg_{i:03d}.mp4")
                    if _extract_video_segment(video_path, seg_start, seg_end, seg_output):
                        segment_files.append(seg_output)
                    else:
                        warnings.append(f"Failed to extract fallback segment {seg_start:.2f}s-{seg_end:.2f}s")
            else:
                # No visual edit for this range â€” extract original segment
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

        # â”€â”€ Step 4: Concatenate all segments preserving codec/resolution/fps â”€â”€
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

        # â”€â”€ Step 3: Overlay remediated audio at correct timestamps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                        warnings.append("Audio overlay failed â€” using video without audio edits")
                        import shutil
                        shutil.copy2(concatenated_path, output_path)
            else:
                # No valid audio files, just copy concatenated to output
                import shutil
                shutil.copy2(concatenated_path, output_path)
        else:
            # No audio edits â€” copy concatenated video to output path
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
            f"Video composition complete â€” output={output_path}, "
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
            "error": "FFmpeg not found â€” ensure FFmpeg is installed and on PATH",
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main â€” test runner for edit_image
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


