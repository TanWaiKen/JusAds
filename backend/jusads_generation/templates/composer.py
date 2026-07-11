"""
templates/composer.py
─────────────────────
Prompt composition logic for the template system.

Resolves prompt templates into generation-ready strings by substituting
user field values into prompt patterns, with session style merging and
validation.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5, 9.3
"""

import json
import logging
import re
from typing import Optional

from google.genai.types import GenerateContentConfig

from shared.clients import gemini
from shared.config import MODEL_TEXT

from . import CompositionResult, SessionContext
from .registry import _REGISTRY

logger = logging.getLogger(__name__)

# Regex to detect unresolved {placeholder} tokens in composed prompts.
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def compose_prompt(
    template_id: str,
    field_values: dict[str, str],
    session_ctx: Optional[SessionContext] = None,
) -> CompositionResult:
    """Compose a generation-ready prompt from template + user field values.

    Algorithm:
    1. Look up template from registry (raise KeyError if not found)
    2. Merge defaults from session's active_style for style-group fields
    3. Override with user-provided field_values
    4. Apply defaults for missing optional fields (use field default or empty string)
    5. Raise ValueError for missing required fields (identify the field name)
    6. Substitute into prompt_pattern (replace {field_name} placeholders)
    7. Build negative_prompt if pattern exists
    8. Validate no unresolved placeholders remain
    9. Return CompositionResult with is_iteration=False, delta_applied=None,
       source_attribution from template
    """
    # Step 1: Resolve template
    if template_id not in _REGISTRY:
        raise KeyError(f"Template not found: {template_id}")
    template = _REGISTRY[template_id]

    # Build set of known field names for filtering unrecognized keys
    known_fields = {field["name"] for field in template["fields"]}

    # Filter user-provided field_values to only known field names
    filtered_values = {
        k: v for k, v in field_values.items() if k in known_fields
    }

    # Step 2: Merge defaults from session (style persistence)
    merged_values: dict[str, str] = {}
    if session_ctx and session_ctx.get("active_style"):
        for field in template["fields"]:
            if (
                field["group"] == "style"
                and field["name"] in session_ctx["active_style"]
            ):
                merged_values[field["name"]] = session_ctx["active_style"][field["name"]]

    # Step 3: Override with user-provided values
    merged_values.update(filtered_values)

    # Step 4: Apply defaults for missing optional fields
    # Step 5: Raise ValueError for missing required fields
    for field in template["fields"]:
        if field["name"] not in merged_values:
            if field["required"]:
                raise ValueError(f"Missing required field: {field['name']}")
            elif field["default"]:
                merged_values[field["name"]] = field["default"]
            else:
                merged_values[field["name"]] = ""

    # Step 6: Substitute into prompt pattern
    composed = template["prompt_pattern"]
    for name, value in merged_values.items():
        composed = composed.replace(f"{{{name}}}", value)

    # Step 7: Build negative prompt if pattern exists
    negative: Optional[str] = None
    if template.get("negative_prompt_pattern"):
        negative = template["negative_prompt_pattern"]
        for name, value in merged_values.items():
            negative = negative.replace(f"{{{name}}}", value)

    # Step 8: Validate no unresolved placeholders remain
    unresolved = _PLACEHOLDER_RE.findall(composed)
    if unresolved:
        logger.warning(
            "[PromptComposer] Unresolved placeholders in composed prompt: %s",
            unresolved,
        )
        raise ValueError(
            f"Unresolved placeholders in composed prompt: {unresolved}"
        )

    logger.info(
        "[PromptComposer] Composed prompt for template '%s' (%d fields resolved)",
        template_id,
        len(merged_values),
    )

    # Step 9: Return CompositionResult
    return CompositionResult(
        composed_prompt=composed,
        negative_prompt=negative,
        template_id=template_id,
        field_values=merged_values,
        source_attribution=template["source"],
        is_iteration=False,
        delta_applied=None,
    )


async def compose_iteration(
    delta_instruction: str,
    session_ctx: SessionContext,
) -> CompositionResult:
    """Produce a new prompt by applying a user delta to the previous turn's prompt.

    Uses Gemini to interpret the delta_instruction against the previous turn's
    field values, merges the changes, and re-composes the prompt while preserving
    all fields not explicitly mentioned in the delta.

    Args:
        delta_instruction: Natural language instruction describing what to change
            (e.g. "make it more red", "change background to tropical").
        session_ctx: Session context containing at least one previous turn.

    Returns:
        CompositionResult with is_iteration=True and delta_applied set.

    Raises:
        ValueError: If session has no previous turns, delta_instruction is empty,
            or Gemini returns unparseable JSON.
        RuntimeError: If Gemini API call fails (timeout, rate limit, network error).
    """
    # Step 1: Get the last turn's state
    if not session_ctx.get("turns"):
        raise ValueError("Cannot iterate: session has no previous turns")
    if not delta_instruction or not delta_instruction.strip():
        raise ValueError("delta_instruction must be a non-empty string")

    last_turn = session_ctx["turns"][-1]
    previous_fields = last_turn["field_values"]
    template_id = last_turn["template_id"]

    if template_id not in _REGISTRY:
        raise KeyError(f"Template not found: {template_id}")
    template = _REGISTRY[template_id]

    # Build list of valid field names for this template
    valid_field_names = [f["name"] for f in template["fields"]]

    # Step 2: Use Gemini to interpret the delta against previous fields
    extraction_prompt = (
        f"Given the previous ad generation with these fields:\n"
        f"{json.dumps(previous_fields, indent=2)}\n\n"
        f'The user wants to modify it with this instruction:\n'
        f'"{delta_instruction}"\n\n'
        f"Return a JSON object with ONLY the fields that should change.\n"
        f"Valid field names: {valid_field_names}\n"
        f"Keep all other fields exactly as they were."
    )

    # Step 3: Call Gemini API
    try:
        response = await gemini.aio.models.generate_content(
            model=MODEL_TEXT,
            contents=extraction_prompt,
            config=GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as e:
        logger.error(
            "[PromptComposer] Gemini API call failed during compose_iteration: %s", e
        )
        raise RuntimeError(
            f"Gemini API call failed during iteration composition: {e}"
        ) from e

    # Step 4: Parse delta fields from LLM response
    try:
        delta_fields = json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(
            "[PromptComposer] Gemini returned unparseable JSON: %s", response.text
        )
        raise ValueError(
            f"Gemini returned unparseable JSON response: {e}"
        ) from e

    # Step 5: Filter out invalid field names
    valid_field_set = set(valid_field_names)
    filtered_delta = {}
    for key, value in delta_fields.items():
        if key in valid_field_set:
            filtered_delta[key] = str(value)
        else:
            logger.warning(
                "[PromptComposer] Filtering invalid field '%s' from Gemini response",
                key,
            )

    # Step 6: Merge previous fields + delta overrides
    updated_fields = {**previous_fields, **filtered_delta}

    # Step 7: Re-compose with updated fields
    result = compose_prompt(template_id, updated_fields, session_ctx)

    # Step 8: Mark as iteration
    result["is_iteration"] = True
    result["delta_applied"] = delta_instruction

    logger.info(
        "[PromptComposer] Iteration composed: %d field(s) changed via delta '%s'",
        len(filtered_delta),
        delta_instruction[:50],
    )

    return result
