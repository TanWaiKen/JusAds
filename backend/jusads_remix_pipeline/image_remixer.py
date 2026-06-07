"""
Image Remixer — Corrects non-compliant images via inpainting or full regeneration.

Takes violation data from the compliance audit and either edits specific
non-compliant regions (inpainting) or generates a completely new compliant
image using the original's composition style as reference.

Uses Gemini Flash Image for both edit (inpainting) and regenerate modes.
Applies cultural rules based on target audience ethnicity.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from jusads_remix_pipeline.config import (
    GEMINI_API_KEY,
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    get_cultural_prompt,
)
from jusads_remix_pipeline.models import ImageRemixOutput, ImageViolation

logger = logging.getLogger(__name__)

# Initialize Gemini client via Vertex AI
client = genai.Client(
    vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION
)

# Model used for image generation/editing
IMAGE_MODEL = "gemini-2.0-flash-exp"

# Output directory for generated images
RESULTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "results"


def remix_image(
    image_path: str,
    violations: list[dict],
    target_audience: dict,
    option: str,
) -> ImageRemixOutput:
    """Correct non-compliant image elements via inpainting or full regeneration.

    Args:
        image_path: Path to the original image file.
        violations: List of image violation dicts, each containing at minimum
            'component', 'location_description', and 'edit_prompt'.
        target_audience: Dict with 'market', 'ethnicity', and optionally 'age_group'.
        option: Remediation method — "edit" (inpainting) or "regenerate" (full).

    Returns:
        ImageRemixOutput with violations, edit_prompt, options, and result_image_path.
    """
    # Requirement 3.8: Empty violations → skip generation, return original unchanged
    if not violations:
        return ImageRemixOutput(
            violations=[],
            edit_prompt="",
            options=["edit", "regenerate"],
            result_image_path=image_path,
        )

    # Parse violations into ImageViolation models for output
    parsed_violations = _parse_violations(violations)

    # Build the combined edit prompt from all violations
    combined_edit_prompt = _build_combined_edit_prompt(violations)

    # Get cultural rules prompt based on target audience ethnicity
    ethnicity = target_audience.get("ethnicity", "")
    cultural_prompt = get_cultural_prompt(ethnicity)

    try:
        if option == "edit":
            result_path = _edit_image(
                image_path=image_path,
                edit_prompt=combined_edit_prompt,
                cultural_prompt=cultural_prompt,
            )
        elif option == "regenerate":
            result_path = _regenerate_image(
                image_path=image_path,
                violations=violations,
                cultural_prompt=cultural_prompt,
                target_audience=target_audience,
            )
        else:
            raise ValueError(f"Invalid option: {option}. Must be 'edit' or 'regenerate'.")

        return ImageRemixOutput(
            violations=parsed_violations,
            edit_prompt=combined_edit_prompt,
            options=["edit", "regenerate"],
            result_image_path=result_path,
        )

    except Exception as e:
        # Requirement 3.7: API error/content filter rejection → return error
        # preserving violations and edit prompt
        logger.error(f"Image remix failed ({option}): {e}")
        return ImageRemixOutput(
            violations=parsed_violations,
            edit_prompt=combined_edit_prompt,
            options=["edit", "regenerate"],
            result_image_path=image_path,
        )


def _edit_image(
    image_path: str,
    edit_prompt: str,
    cultural_prompt: str,
) -> str:
    """Edit the image using Gemini Flash Image inpainting.

    Uses the edit prompt from violations to modify only non-compliant regions
    while preserving layout, background, and non-violating elements.

    Args:
        image_path: Path to the original image.
        edit_prompt: Combined edit prompt describing what to fix.
        cultural_prompt: Cultural rules prompt instructions.

    Returns:
        Path to the generated result image.
    """
    # Load the original image
    image_bytes = Path(image_path).read_bytes()
    mime_type = _get_mime_type(image_path)

    # Build the full prompt for inpainting
    full_prompt = _build_inpainting_prompt(edit_prompt, cultural_prompt)

    # Call Gemini with the image and edit instructions
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=full_prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.4,
        ),
    )

    # Extract and save the generated image
    result_path = _save_generated_image(response)
    return result_path


def _regenerate_image(
    image_path: str,
    violations: list[dict],
    cultural_prompt: str,
    target_audience: dict,
) -> str:
    """Generate a completely new compliant image using original as style reference.

    Uses the original image's composition style (photorealistic, illustrated,
    or graphic) as a reference to produce a fully compliant replacement.

    Args:
        image_path: Path to the original image (used as style reference).
        violations: List of violation dicts for context.
        cultural_prompt: Cultural rules prompt instructions.
        target_audience: Target audience information.

    Returns:
        Path to the generated result image.
    """
    # Load the original image as style reference
    image_bytes = Path(image_path).read_bytes()
    mime_type = _get_mime_type(image_path)

    # Build regeneration prompt
    full_prompt = _build_regeneration_prompt(violations, cultural_prompt, target_audience)

    # Call Gemini with the original image as reference and regeneration instructions
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=full_prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.6,
        ),
    )

    # Extract and save the generated image
    result_path = _save_generated_image(response)
    return result_path


def _build_inpainting_prompt(edit_prompt: str, cultural_prompt: str) -> str:
    """Build the prompt for inpainting (edit) mode.

    Instructs the model to modify only the non-compliant regions described
    in the edit prompt while preserving everything else.
    """
    parts = [
        "Edit this advertisement image to fix the following compliance violations.",
        "IMPORTANT: Preserve the overall layout, background, and all non-violating elements.",
        "Only modify the specific non-compliant regions described below.",
        "",
        f"## EDIT INSTRUCTIONS\n{edit_prompt}",
    ]

    if cultural_prompt:
        parts.append(f"\n## CULTURAL RULES (MUST FOLLOW)\n{cultural_prompt}")

    parts.append(
        "\nGenerate the corrected image maintaining the same composition and style."
    )

    return "\n".join(parts)


def _build_regeneration_prompt(
    violations: list[dict],
    cultural_prompt: str,
    target_audience: dict,
) -> str:
    """Build the prompt for full image regeneration.

    Instructs the model to generate a completely new compliant image
    using the provided image's composition style as reference.
    """
    # Summarize what needs to be fixed
    violation_summary = "\n".join(
        f"- {v.get('component', 'Unknown')}: {v.get('edit_prompt', v.get('location_description', ''))}"
        for v in violations
    )

    ethnicity = target_audience.get("ethnicity", "")
    market = target_audience.get("market", "Malaysia")

    parts = [
        "Generate a completely new advertisement image that is fully compliant.",
        "Use the provided image ONLY as a style and composition reference.",
        "The new image must fix ALL of the following violations:",
        "",
        f"## VIOLATIONS TO FIX\n{violation_summary}",
    ]

    if cultural_prompt:
        parts.append(f"\n## CULTURAL RULES (MUST FOLLOW)\n{cultural_prompt}")

    parts.extend([
        f"\n## TARGET AUDIENCE",
        f"Market: {market}",
        f"Ethnicity: {ethnicity}" if ethnicity else "",
        "",
        "## REQUIREMENTS",
        "- Maintain the same visual style (photorealistic/illustrated/graphic) as the reference image",
        "- Keep the same product/brand elements if visible",
        "- Ensure the new image is fully compliant with all cultural rules",
        "- Generate a high-quality advertisement image suitable for commercial use",
    ])

    return "\n".join(parts)


def _parse_violations(violations: list[dict]) -> list[ImageViolation]:
    """Parse raw violation dicts into ImageViolation model instances.

    Handles missing or malformed fields gracefully by using defaults.
    """
    parsed = []
    for i, v in enumerate(violations):
        try:
            parsed.append(
                ImageViolation(
                    index=v.get("index", i),
                    type=v.get("type", "visual"),
                    component=v.get("component", ""),
                    severity=v.get("severity", "error"),
                    location_description=v.get("location_description", ""),
                    edit_prompt=v.get("edit_prompt", ""),
                )
            )
        except Exception as e:
            logger.warning(f"Failed to parse violation at index {i}: {e}")
    return parsed


def _build_combined_edit_prompt(violations: list[dict]) -> str:
    """Combine edit prompts from all violations into a single prompt.

    Each violation's edit_prompt describes how to fix that specific issue.
    """
    prompts = []
    for v in violations:
        edit_prompt = v.get("edit_prompt", "")
        if edit_prompt:
            component = v.get("component", "Unknown component")
            prompts.append(f"[{component}]: {edit_prompt}")

    return "\n".join(prompts) if prompts else ""


def _save_generated_image(response: Any) -> str:
    """Extract the generated image from the Gemini response and save to disk.

    Args:
        response: The Gemini API response containing the generated image.

    Returns:
        Path to the saved image file.

    Raises:
        RuntimeError: If no image was found in the response.
    """
    # Ensure output directory exists
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Look for image parts in the response
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                # Determine file extension from MIME type
                ext = _mime_to_extension(part.inline_data.mime_type)
                filename = f"remix_{uuid.uuid4().hex[:12]}{ext}"
                output_path = RESULTS_DIR / filename

                output_path.write_bytes(part.inline_data.data)
                logger.info(f"Saved remixed image to: {output_path}")
                return str(output_path)

    raise RuntimeError(
        "No image generated in response. The request may have been "
        "blocked by content filters or the model did not produce an image."
    )


def _get_mime_type(image_path: str) -> str:
    """Determine MIME type from file extension."""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/png")


def _mime_to_extension(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return ext_map.get(mime_type, ".png")
