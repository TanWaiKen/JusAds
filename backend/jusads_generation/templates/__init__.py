"""
templates/__init__.py
─────────────────────
Data models and type definitions for the prompt template system.

All types are defined as ``TypedDict`` per project conventions for LangGraph
state compatibility. Provides structured, field-based prompt composition per
ad type (poster, carousel, video).

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from typing import Literal, Optional, TypedDict

# ─── Ad Types ─────────────────────────────────────────────────────────────────

AdType = Literal["poster", "carousel", "video", "image", "text", "audio"]

# ─── Template Field Definition ────────────────────────────────────────────────


class FieldOption(TypedDict):
    """A predefined option for a select/tag field."""

    value: str
    label: str
    preview_url: Optional[str]  # thumbnail for visual options


class TemplateField(TypedDict):
    """One fillable field within a prompt template."""

    name: str                   # machine key (e.g. "subject")
    label: str                  # human label (e.g. "Main Subject")
    field_type: Literal["text", "textarea", "select", "tags", "color", "number"]
    required: bool
    default: Optional[str]
    placeholder: Optional[str]
    help_text: Optional[str]    # guidance sourced from SD/SDXL best practices
    options: Optional[list[FieldOption]]  # for select/tags types
    max_length: Optional[int]
    group: Optional[str]        # UI grouping ("composition", "style", "technical")


# ─── Prompt Template ──────────────────────────────────────────────────────────


class PromptSource(TypedDict):
    """Attribution for the prompt pattern source."""

    name: str           # e.g. "Stable Diffusion Community"
    url: Optional[str]  # link to source
    model: str          # e.g. "SDXL 1.0", "SeaArt v3"


class PromptTemplate(TypedDict):
    """A complete prompt template for one ad type."""

    template_id: str            # unique ID (e.g. "poster_product_hero")
    ad_type: AdType
    name: str                   # human-readable name
    description: str            # what this template produces
    source: PromptSource        # open-source attribution
    fields: list[TemplateField]
    prompt_pattern: str         # the composable pattern with {field_name} placeholders
    negative_prompt_pattern: Optional[str]
    example_output_url: Optional[str]  # sample generated image
    tags: list[str]             # searchable tags ("minimalist", "product-hero", etc.)


# ─── Session Memory ───────────────────────────────────────────────────────────


class GenerationTurn(TypedDict):
    """One generation turn stored in session memory."""

    turn_id: str
    template_id: Optional[str]
    field_values: dict[str, str]
    composed_prompt: str
    negative_prompt: Optional[str]
    output_urls: list[str]
    ad_type: AdType
    timestamp: str  # ISO 8601


class SessionContext(TypedDict):
    """Session memory state for iterative generation."""

    project_id: str
    task_id: str
    turns: list[GenerationTurn]
    active_style: Optional[dict[str, str]]  # locked style params from last turn
    active_template_id: Optional[str]


# ─── Composition Result ───────────────────────────────────────────────────────


class CompositionResult(TypedDict):
    """Output of prompt composition, passed to the orchestrator."""

    composed_prompt: str
    negative_prompt: Optional[str]
    template_id: str
    field_values: dict[str, str]
    source_attribution: PromptSource
    is_iteration: bool
    delta_applied: Optional[str]  # what changed from previous turn
