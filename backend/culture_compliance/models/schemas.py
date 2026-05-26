"""Pydantic models for the content compliance pipeline.

Defines input, state, and output models for multi-modal content compliance
evaluation against Malaysia (MCMC) and Singapore (IMDA/ASAS) guidelines.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --- Enums ---


class ContentType(str, Enum):
    """Supported content types for compliance evaluation."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class Market(str, Enum):
    """Supported regulatory markets."""

    MALAYSIA = "malaysia"
    SINGAPORE = "singapore"


# --- Violation Categories and Severity ---

VIOLATION_CATEGORIES = Literal[
    "Religious Sensitivity",
    "Ethnic/Racial",
    "Sexual/Explicit",
    "Political/State",
    "LGBTQ",
    "Profanity",
]

SEVERITY_LEVELS = Literal["Severe", "Moderate", "Minor"]


# --- Input Models ---


class ContentSubmission(BaseModel):
    """Input to the compliance pipeline.

    Represents a single piece of content to be evaluated for regulatory
    compliance. Content can be raw text, a base64-encoded image, or an
    S3 URI for video files.
    """

    content: str = Field(
        ...,
        description="Text content, base64-encoded image, or S3 URI for video",
    )
    content_type: ContentType
    market: Market = Market.MALAYSIA
    frame_interval_seconds: float = Field(
        default=1.0,
        ge=0.5,
        le=5.0,
        description="Frame sampling interval for video (seconds)",
    )

    target_ethnicity: str = Field(
        default="all",
        pattern="^(malay|chinese|indian|all)$",
        description="Target ethnic audience for cultural guideline filtering",
    )
    target_age_group: str = Field(
        default="all_ages",
        pattern="^(all_ages|adults_only|children)$",
        description="Target age group for cultural guideline filtering",
    )

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Validate that content is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Content must not be empty or whitespace-only")
        return v


# --- Issue Location Models ---


class TextIssueLocation(BaseModel):
    """Localization for text content issues.

    Identifies a specific problematic phrase in the original text with its
    character offset, enabling frontend inline highlighting.
    """

    phrase: str = Field(
        ...,
        max_length=200,
        description="Verbatim problematic substring from the input",
    )
    char_offset: int = Field(
        ...,
        ge=0,
        description="0-based character offset in original text",
    )
    category: VIOLATION_CATEGORIES
    severity: SEVERITY_LEVELS
    guideline_source: Literal["regulatory", "cultural"] = "regulatory"


class ImageIssueLocation(BaseModel):
    """Localization for image content issues.

    Identifies a problematic region in an image using a bounding box
    expressed as percentages of image dimensions (0-100).
    """

    bounding_box: dict = Field(
        ...,
        description="x, y, width, height as percentage (0-100) of image dimensions",
    )
    description: str = Field(..., max_length=200)
    category: VIOLATION_CATEGORIES
    severity: SEVERITY_LEVELS
    guideline_source: Literal["regulatory", "cultural"] = "regulatory"

    @field_validator("bounding_box")
    @classmethod
    def validate_bbox(cls, v: dict) -> dict:
        """Validate bounding box contains required keys with values in 0-100 range."""
        required = {"x", "y", "width", "height"}
        if not required.issubset(v.keys()):
            raise ValueError(f"Bounding box must contain: {required}")
        for key in required:
            val = v[key]
            if not isinstance(val, (int, float)):
                raise ValueError(f"{key} must be a number")
            if not (0 <= val <= 100):
                raise ValueError(f"{key} must be between 0 and 100")
        return v


class VideoIssueLocation(BaseModel):
    """Localization for video content issues.

    Identifies a problematic moment in a video using a timestamp,
    enabling frontend linking to the specific video position.
    """

    timestamp: str = Field(
        ...,
        description="Format: MM:SS or HH:MM:SS",
    )
    description: str = Field(..., max_length=200)
    category: VIOLATION_CATEGORIES
    severity: SEVERITY_LEVELS
    guideline_source: Literal["regulatory", "cultural"] = "regulatory"


# --- Processing and Error Models ---


class ProcessingMetadata(BaseModel):
    """Metadata about pipeline execution."""

    pipeline_duration_ms: int
    models_used: list[str]
    market: str


class PipelineWarning(BaseModel):
    """Warning about partial pipeline failure.

    Indicates that a pipeline step encountered an issue but the pipeline
    continued processing with available data.
    """

    step_name: str
    description: str
    result_may_be_incomplete: bool


class PipelineError(BaseModel):
    """Error response when pipeline cannot produce a result.

    Used when the pipeline encounters a fatal error that prevents
    producing a valid ComplianceResult.
    """

    error_type: Literal["validation", "service_unavailable", "timeout", "parse_error"]
    message: str
    details: Optional[dict] = None


# --- Output Models ---


class ComplianceResult(BaseModel):
    """Final output of the compliance pipeline.

    Contains the complete compliance evaluation including risk scoring,
    localized issue indicators, and processing metadata.
    """

    content_type: ContentType
    market: Market
    risk_level: Literal["High", "Medium", "Low"]
    score: int = Field(..., ge=0, le=100)
    high_risk_indicators: list[
        TextIssueLocation | ImageIssueLocation | VideoIssueLocation
    ] = Field(default_factory=list, max_length=10)
    explanation: str = Field(..., max_length=500)
    suggestion: str = Field(..., max_length=400)
    processing_metadata: ProcessingMetadata
    warnings: list[PipelineWarning] = Field(default_factory=list)


# --- Pipeline State Model ---


class PipelineState(BaseModel):
    """LangGraph state object passed between nodes.

    Contains all intermediate data as content flows through the pipeline,
    from initial submission through processing, evaluation, and result formatting.
    """

    # Input
    submission: ContentSubmission

    # Routing
    content_type: ContentType
    market: Market

    # Processing intermediates
    extracted_text: Optional[str] = None
    visual_description: Optional[str] = None
    unified_content: Optional[str] = None
    frame_descriptions: Optional[list[dict]] = None
    transcript_segments: Optional[list[dict]] = None

    # Cultural targeting
    target_ethnicity: str = "all"
    target_age_group: str = "all_ages"

    # Guidelines
    regulatory_guidelines: Optional[str] = None
    cultural_guidelines: Optional[str] = None
    retrieved_guidelines: Optional[str] = None
    guideline_collection: Optional[str] = None
    guideline_sources: list[dict] = Field(default_factory=list)

    # Persona narrative (v3 single-model video pipeline)
    persona_narrative: Optional[str] = None

    # Evaluation
    raw_llm_output: Optional[dict] = None

    # Result
    compliance_result: Optional[dict] = None

    # Error tracking
    errors: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)

    # Metadata
    pipeline_start_ms: Optional[int] = None
    models_used: list[str] = Field(default_factory=list)
