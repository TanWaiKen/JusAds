"""Storyboard Generator for the JusAds Video Remix Pipeline.

Generates key storyboard frames for each video chunk using Gemini Flash Image.
All frames for a chunk are produced in a SINGLE API call (efficient — not
frame-by-frame). Applies cultural rules and brand context to generation prompts.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1, 11.4
"""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from jusads_remix_pipeline.config import (
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    get_cultural_prompt,
)

logger = logging.getLogger(__name__)

# Initialize Gemini client via Vertex AI
client = genai.Client(
    vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION
)

# Model used for storyboard frame generation (same as image_remixer)
IMAGE_MODEL = "gemini-2.0-flash-exp"

# Maximum retry attempts on failure (Req 5.5, 11.4)
MAX_RETRIES = 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def generate_storyboard(
    chunk: dict,
    target_audience: dict,
    brand_context: dict,
) -> dict:
    """Generate storyboard key frames for a video chunk.

    Produces 2-4 key frames in a single Gemini Flash Image API call.
    The number of frames is determined by chunk duration:
      - ≤4 seconds → 2 frames
      - ≤6 seconds → 3 frames
      - ≤8 seconds → 4 frames

    Applies cultural rules for the target audience and includes brand
    elements (product packaging, logos, color palette) in the generation prompt.

    Args:
        chunk: Dict from segment_planner containing:
            - start_time (float): Chunk start in seconds
            - end_time (float): Chunk end in seconds
            - source_violation_index (int): Which violation this chunk belongs to
            - chunk_sequence_number (int): Sequence within the violation
            - is_short_form (bool): True if original segment < 5 seconds
        target_audience: Dict with audience info:
            - ethnicity (str): e.g. "Malay", "Chinese"
            - market (str): e.g. "Malaysia", "Singapore"
            - gender (str, optional): e.g. "male", "female"
        brand_context: Dict with brand/product info:
            - product_name (str): Name of the product being advertised
            - brand_colors (list[str]): Brand color palette
            - logo_description (str): Description of the brand logo
            - product_description (str, optional): Product description
            - packaging_description (str, optional): Product packaging details

    Returns:
        Dict with:
            - chunk_index (int): source_violation_index from chunk
            - frames (list[bytes]): Raw image bytes for each generated frame
            - frame_count (int): Number of frames generated
            - duration (float): Chunk duration in seconds
            - error (str | None): Error message if generation failed
    """
    start_time = chunk.get("start_time", 0.0)
    end_time = chunk.get("end_time", 0.0)
    chunk_index = chunk.get("source_violation_index", 0)
    duration = end_time - start_time

    # Determine number of frames based on duration (Req 5.1, 11.1)
    frame_count = _determine_frame_count(duration)

    # Build the generation prompt with cultural rules and brand context
    prompt = _build_storyboard_prompt(
        frame_count=frame_count,
        duration=duration,
        target_audience=target_audience,
        brand_context=brand_context,
    )

    # Attempt generation with retries (Req 5.5, 11.4)
    last_error: str | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            frames = _call_gemini_for_frames(prompt, frame_count)
            if frames:
                logger.info(
                    f"Storyboard generated for chunk {chunk_index}: "
                    f"{len(frames)} frames (attempt {attempt + 1})"
                )
                return {
                    "chunk_index": chunk_index,
                    "frames": frames,
                    "frame_count": len(frames),
                    "duration": duration,
                    "error": None,
                }
            else:
                last_error = "No frames returned from generation API"
                logger.warning(
                    f"Storyboard attempt {attempt + 1} for chunk {chunk_index}: "
                    f"no frames returned"
                )
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Storyboard attempt {attempt + 1} for chunk {chunk_index} "
                f"failed: {e}"
            )

    # All attempts failed (Req 5.5) — return error with chunk index and reason
    logger.error(
        f"Storyboard generation failed for chunk {chunk_index} "
        f"after {1 + MAX_RETRIES} attempts: {last_error}"
    )
    return {
        "chunk_index": chunk_index,
        "frames": [],
        "frame_count": 0,
        "duration": duration,
        "error": (
            f"Storyboard generation failed for chunk {chunk_index} "
            f"after {1 + MAX_RETRIES} attempts: {last_error}"
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIVATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _determine_frame_count(duration: float) -> int:
    """Determine the number of storyboard frames based on chunk duration.

    Req 5.1: 2 frames for ≤4s, 3 frames for ≤6s, 4 frames for ≤8s.
    """
    if duration <= 4.0:
        return 2
    elif duration <= 6.0:
        return 3
    else:
        return 4


def _build_storyboard_prompt(
    frame_count: int,
    duration: float,
    target_audience: dict,
    brand_context: dict,
) -> str:
    """Build the Gemini prompt for storyboard frame generation.

    Includes cultural rules (Req 5.2, 5.3) and brand elements (Req 5.4).
    """
    ethnicity = target_audience.get("ethnicity", "")
    market = target_audience.get("market", "Malaysia")

    # Cultural rules prompt (Req 5.2, 5.3)
    cultural_prompt = get_cultural_prompt(ethnicity)

    # Brand context elements (Req 5.4)
    product_name = brand_context.get("product_name", "")
    brand_colors = brand_context.get("brand_colors", [])
    logo_description = brand_context.get("logo_description", "")
    product_description = brand_context.get("product_description", "")
    packaging_description = brand_context.get("packaging_description", "")

    parts: list[str] = [
        f"Generate exactly {frame_count} storyboard key frames for a {duration:.1f}-second "
        f"video advertisement clip.",
        "",
        "Each frame should represent a distinct moment in the clip's visual narrative, "
        "evenly spaced across the clip duration. The frames should flow naturally as a "
        "sequence that can be interpolated into smooth video.",
        "",
        f"## FRAME REQUIREMENTS",
        f"- Generate exactly {frame_count} distinct frames in this single image",
        f"- Arrange frames as a {frame_count}-panel storyboard grid",
        f"- Each frame represents a key moment in the {duration:.1f}s clip",
        "- Frames should show clear visual progression/movement between them",
        "- Style: photorealistic advertisement quality",
    ]

    # Brand elements (Req 5.4)
    if product_name or brand_colors or logo_description:
        parts.append("")
        parts.append("## BRAND ELEMENTS (MUST APPEAR IN FRAMES)")
        if product_name:
            parts.append(f"- Product: {product_name}")
        if product_description:
            parts.append(f"- Product description: {product_description}")
        if packaging_description:
            parts.append(f"- Product packaging: {packaging_description}")
        if logo_description:
            parts.append(f"- Brand logo: {logo_description}")
        if brand_colors:
            color_str = ", ".join(brand_colors)
            parts.append(f"- Brand color palette: {color_str}")

    # Cultural rules (Req 5.2, 5.3)
    if cultural_prompt:
        parts.append("")
        parts.append("## CULTURAL RULES (MUST FOLLOW STRICTLY)")
        parts.append(cultural_prompt)

    # Target audience context
    parts.append("")
    parts.append("## TARGET AUDIENCE")
    parts.append(f"- Market: {market}")
    if ethnicity:
        parts.append(f"- Ethnicity: {ethnicity}")

    parts.append("")
    parts.append("## OUTPUT FORMAT")
    parts.append(
        f"Generate a single image containing {frame_count} storyboard panels "
        "arranged in a grid. Each panel is a distinct key frame for video interpolation."
    )

    return "\n".join(parts)


def _call_gemini_for_frames(prompt: str, expected_frame_count: int) -> list[bytes]:
    """Call Gemini Flash Image API to generate storyboard frames.

    Makes a single API call requesting multiple frames (Req 11.1).

    Args:
        prompt: The fully constructed generation prompt.
        expected_frame_count: Number of frames requested.

    Returns:
        List of image bytes for each generated frame. May return fewer
        frames than requested if the model produces a single storyboard image.
    """
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            types.Content(
                parts=[types.Part.from_text(text=prompt)]
            )
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.5,
        ),
    )

    # Extract all image parts from the response
    frames: list[bytes] = []
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                frames.append(part.inline_data.data)

    return frames
