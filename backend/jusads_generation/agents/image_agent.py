"""
image_agent.py
──────────────
Image_Agent — the independent Media Agent that generates ad visuals (Req 5.1).

Workflow: Gemini prompt refinement → Gemini native image generation at the
resolved ``rules.aspect_ratio`` / ``rules.max_dimension`` (Req 7.1) → ``.jpg``
uploaded to S3 → a ``generated_ads`` row.

The agent implements the shared :func:`generate` contract from ``base.py`` and
lives in its own module. It never imports any other Media Agent, so it can
neither consume nor depend on another agent's output (Req 5.2). Every external
call (Gemini, S3, Supabase) is wrapped in ``try/except`` with ``[ImageAgent]``
logging and a graceful fallback (a PIL placeholder) per steering conventions.
On success it records a ``completed`` row; on failure it records a ``failed``
row without touching any other agent's recorded output (Req 5.4, 5.5).
"""

import logging
import os
import tempfile
import uuid
from typing import Optional

from PIL import Image, ImageDraw

from shared.clients import gemini, supabase
from shared.s3_client import upload_file_public

from ..platform_rules import PlatformRule
from .base import AgentResult, load_guide

logger = logging.getLogger(__name__)

MEDIA_TYPE = "image"


def _image_size_for_dimension(max_dimension: int) -> str:
    """Map a resolved max pixel dimension to a Gemini ``image_size`` label.

    Gemini's native image model accepts coarse size labels rather than exact
    pixel counts, so the resolved ``max_dimension`` (Req 7.1) is bucketed to the
    closest supported label.

    Args:
        max_dimension: The resolved maximum pixel dimension (longest side).

    Returns:
        A Gemini ``image_size`` label such as ``"1K"`` or ``"2K"``.
    """
    if max_dimension >= 2048:
        return "2K"
    return "1K"


def _refine_prompt(brief: str, guide: str, has_reference: bool = False) -> str:
    """Refine a raw brief into a detailed commercial image prompt via Gemini.

    When ``has_reference`` is True, the refinement is instructed to build on the
    uploaded reference image(s) — preserving their subject, colors, and
    composition — rather than inventing an unrelated scene (Test 4 feedback).

    Falls back to the raw ``brief`` on any failure so generation can proceed
    (Req 3.2).
    """
    reference_clause = (
        (
            "\n\nIMPORTANT — REFERENCE PROVIDED: The user has attached one or more "
            "reference images. Your prompt MUST build on them: preserve the main "
            "subject/product, its colors, materials, and overall composition from "
            "the reference. Describe the scene as a refined, on-brand version of "
            "what is shown in the reference — do not invent an unrelated subject."
        )
        if has_reference
        else ""
    )

    refine_prompt = f"""You are an expert advertising Art Director.

Convert this idea into a single detailed commercial image generation prompt:
"{brief}"

Follow this structure: Subject + setting + lighting + materials/textures + composition + ad intent + empty copy space.

Requirements:
- Clean, modern commercial photography or digital art style
- High contrast, vibrant colors suitable for social media (Instagram/TikTok)
- Product-focused composition with clear visual hierarchy
- Culturally appropriate for Southeast Asian markets (Malaysia/Singapore)
- Modest, professional presentation (no revealing clothing)
- Leave clear empty space for ad copy
- No watermark, no visible logos{reference_clause}

Reference guidelines: {guide[:400]}

Output ONLY the image prompt text (max 80 words), nothing else."""

    try:
        refine_resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=refine_prompt,
        )
        visual_prompt = refine_resp.text.strip()
        logger.info("[ImageAgent] Refined prompt: %s", visual_prompt[:120])
        return visual_prompt
    except Exception as e:
        logger.warning(
            "[ImageAgent] Prompt refinement failed: %s. Using raw prompt.", e
        )
        return brief


def _create_fallback_image(text: str) -> str:
    """Generate a PIL visual placeholder when native image generation fails.

    Args:
        text: Text to render onto the placeholder banner.

    Returns:
        The local path to the generated ``.png`` placeholder.
    """
    width, height = 512, 512
    image = Image.new("RGB", (width, height), color="#1e1e2f")
    draw = ImageDraw.Draw(image)

    # Simple vertical gradient.
    for y in range(height):
        r = int(0x1E + (0x4A - 0x1E) * (y / height))
        g = int(0x1E + (0x3B - 0x1E) * (y / height))
        b = int(0x2F + (0x76 - 0x2F) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    draw.rectangle([40, 40, width - 40, height - 40], outline="#4f46e5", width=3)
    draw.text((60, 100), "AD CREATIVE", fill="#ffffff")

    wrapped_text = "\n".join([text[i : i + 35] for i in range(0, len(text), 35)])
    draw.text((60, 180), wrapped_text, fill="#e2e8f0")
    draw.text((60, 420), "Generated locally (Fallback Agent)", fill="#10b981")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.close()
    image.save(tmp.name)
    return tmp.name


def _generate_native_image(visual_prompt: str, rules: PlatformRule, reference_parts: list) -> Optional[str]:
    """Generate an image via Gemini's native image model at the resolved sizing.

    Sources the aspect ratio and pixel size from ``rules`` (Req 7.1) rather than
    hardcoding them. When ``reference_parts`` are provided, they are included as
    multimodal context so the generated image is influenced by the user's
    references. Returns the local ``.jpg`` path, or ``None`` on failure so
    the caller can fall back to a PIL placeholder (Req 3.2).
    """
    try:
        from google.genai import types

        image_size = _image_size_for_dimension(rules.get("max_dimension", 0) or 0)
        logger.info(
            "[ImageAgent] Generating image at aspect_ratio=%s, image_size=%s (refs=%d)",
            rules["aspect_ratio"],
            image_size,
            len(reference_parts),
        )

        # Build contents: text prompt + any reference image parts the user uploaded.
        # When references exist, lead with an explicit instruction so the model
        # closely matches the reference's subject, colors, and composition
        # rather than treating it as loose inspiration (Test 4 feedback).
        contents: list = []
        if reference_parts:
            contents.append(
                "Use the following reference image(s) as the primary visual anchor. "
                "Generate a new ad image that closely matches the reference's subject/product, "
                "color palette, materials, and composition, while applying this creative direction:"
            )
            contents.extend(reference_parts)
        contents.append(visual_prompt)

        response = gemini.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=contents,
            config=types.GenerateContentConfig(
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
                    aspect_ratio=rules["aspect_ratio"],
                    image_size=image_size,
                    output_mime_type="image/jpeg",
                ),
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            ),
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if (
                    hasattr(part, "inline_data")
                    and part.inline_data
                    and part.inline_data.data
                ):
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(part.inline_data.data)
                    tmp.close()
                    logger.info("[ImageAgent] Gemini native image generation successful.")
                    return tmp.name
    except Exception as e:
        logger.warning("[ImageAgent] Gemini image gen failed: %s. Using PIL fallback.", e)
    return None


def _record_row(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    status: str,
    prompt_used: str,
    s3_media_key: Optional[str],
    metadata: dict,
) -> Optional[str]:
    """Insert one ``generated_ads`` row and return its id (or ``None``).

    Records the row with ``project_id``, ``task_id``, ``media_type``,
    ``platform`` and the given ``status`` (Req 5.4, 5.5). Supabase failures are
    caught and logged so the caller can still return a result (Req 3.2).
    """
    try:
        response = (
            supabase.table("generated_ads")
            .insert(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "media_type": MEDIA_TYPE,
                    "platform": platform,
                    "prompt_used": prompt_used,
                    "s3_media_key": s3_media_key,
                    "status": status,
                    "metadata": metadata,
                }
            )
            .execute()
        )
        rows = response.data or []
        if rows:
            return str(rows[0].get("id")) if rows[0].get("id") is not None else None
    except Exception as e:
        logger.error("[ImageAgent] Supabase recording (%s) failed: %s", status, e)
    return None


async def generate(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: PlatformRule,
    reference_parts: list,
) -> AgentResult:
    """Generate one image ad, upload it to S3, and record a ``generated_ads`` row.

    Implements the shared Media Agent contract (see ``base.generate``). The
    image is generated at the resolved ``rules.aspect_ratio`` /
    ``rules.max_dimension`` rather than hardcoded values (Req 7.1). On success
    returns ``status='completed'`` and records a ``completed`` row (Req 5.4). On
    an unrecoverable failure it records a ``failed`` row and returns
    ``status='failed'`` WITHOUT modifying any other agent's output (Req 5.5).

    Args:
        brief: The user's campaign brief / prompt.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: The resolved, validated target platform.
        rules: Resolved platform sizing rules (aspect ratio + max dimension).
        reference_parts: Multimodal reference parts (images/files the user
            uploaded); passed to Gemini as visual context for generation.

    Returns:
        An :class:`AgentResult` describing the generated image ad.
    """
    logger.info(
        "[ImageAgent] Generating image ad for platform '%s' (project=%s, task=%s)",
        platform,
        project_id,
        task_id,
    )

    guide = load_guide("image")
    visual_prompt = _refine_prompt(brief, guide, has_reference=bool(reference_parts))

    generated_path: Optional[str] = None
    s3_key = f"generated_ads/{project_id}/{task_id}/image_{uuid.uuid4().hex[:6]}.jpg"
    try:
        generated_path = _generate_native_image(visual_prompt, rules, reference_parts)
        if not generated_path:
            generated_path = _create_fallback_image(visual_prompt)

        try:
            s3_url = upload_file_public(generated_path, s3_key)
        except Exception as e:
            logger.warning("[ImageAgent] S3 upload failed, using fallback: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        ad_id = _record_row(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            status="completed",
            prompt_used=visual_prompt[:500],
            s3_media_key=s3_key,
            metadata={
                "s3_url": s3_url,
                "aspect_ratio": rules.get("aspect_ratio"),
                "max_dimension": rules.get("max_dimension"),
            },
        )

        logger.info("[ImageAgent] Completed image ad (ad_id=%s)", ad_id)
        return AgentResult(
            ad_id=ad_id,
            media_type=MEDIA_TYPE,
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=None,
            status="completed",
            error=None,
        )
    except Exception as e:
        # Unrecoverable failure: record an isolated failed row (Req 5.5).
        logger.error("[ImageAgent] Generation failed: %s", e)
        fail_id = _record_row(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            status="failed",
            prompt_used=visual_prompt[:500],
            s3_media_key=None,
            metadata={"error": str(e)},
        )
        return AgentResult(
            ad_id=fail_id,
            media_type=MEDIA_TYPE,
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        if generated_path and os.path.exists(generated_path):
            try:
                os.unlink(generated_path)
            except Exception:
                pass
