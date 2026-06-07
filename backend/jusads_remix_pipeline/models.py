"""Violation data models and remix output schemas for the JusAds Remix Pipeline.

Defines Pydantic models for all four media types (text, image, audio, video)
with field validation per Requirements 9.1–9.6.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Literal


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIOLATION MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TextViolation(BaseModel):
    """Text violation record (Requirement 9.1).

    Fields:
        index: Non-negative integer identifying the violation.
        type: Must be "text".
        phrase: The non-compliant phrase (max 500 chars).
        severity: One of "error" or "warning".
        reason: Explanation of the violation (max 1000 chars).
        suggested_replacement: Compliant alternative (max 500 chars).
    """

    index: int = Field(..., ge=0, description="Non-negative violation index")
    type: Literal["text"] = Field(..., description='Must be "text"')
    phrase: str = Field(..., max_length=500, description="Non-compliant phrase")
    severity: Literal["error", "warning"] = Field(
        ..., description='Severity level: "error" or "warning"'
    )
    reason: str = Field(..., max_length=1000, description="Reason for violation")
    suggested_replacement: str = Field(
        ..., max_length=500, description="Suggested compliant replacement"
    )


class ImageViolation(BaseModel):
    """Image violation record (Requirement 9.2).

    Fields:
        index: Non-negative integer identifying the violation.
        type: Must be "visual".
        component: The non-compliant visual component (max 200 chars).
        severity: One of "error" or "warning".
        location_description: Where in the image the violation occurs (max 1000 chars).
        edit_prompt: Prompt for fixing the violation (max 2000 chars).
    """

    index: int = Field(..., ge=0, description="Non-negative violation index")
    type: Literal["visual"] = Field(..., description='Must be "visual"')
    component: str = Field(
        ..., max_length=200, description="Non-compliant visual component"
    )
    severity: Literal["error", "warning"] = Field(
        ..., description='Severity level: "error" or "warning"'
    )
    location_description: str = Field(
        ..., max_length=1000, description="Location of violation in image"
    )
    edit_prompt: str = Field(
        ..., max_length=2000, description="Prompt for fixing the violation"
    )


class AudioViolation(BaseModel):
    """Audio violation record (Requirement 9.3).

    Fields:
        index: Non-negative integer identifying the violation.
        type: Must be "audio".
        spoken_phrase: The non-compliant spoken phrase (max 500 chars).
        severity: One of "error" or "warning".
        reason: Explanation of the violation (max 1000 chars).
        suggested_replacement: Compliant alternative (max 500 chars).
        voice_gender: One of "male" or "female".
    """

    index: int = Field(..., ge=0, description="Non-negative violation index")
    type: Literal["audio"] = Field(..., description='Must be "audio"')
    spoken_phrase: str = Field(
        ..., max_length=500, description="Non-compliant spoken phrase"
    )
    severity: Literal["error", "warning"] = Field(
        ..., description='Severity level: "error" or "warning"'
    )
    reason: str = Field(..., max_length=1000, description="Reason for violation")
    suggested_replacement: str = Field(
        ..., max_length=500, description="Suggested compliant replacement"
    )
    voice_gender: Literal["male", "female"] = Field(
        ..., description='Voice gender: "male" or "female"'
    )


class VideoViolation(BaseModel):
    """Video violation record (Requirements 9.4, 9.6).

    Fields:
        index: Non-negative integer identifying the violation.
        start: Start time in seconds (non-negative).
        end: End time in seconds (non-negative, must be > start).
        type: One of "visual" or "audio".
        category: Category of violation (max 200 chars).
        severity: One of "error" or "warning".
        description: Description of the violation (max 1000 chars).
        clip_url: URL to the violation clip (max 500 chars).
    """

    index: int = Field(..., ge=0, description="Non-negative violation index")
    start: float = Field(..., ge=0, description="Start time in seconds (non-negative)")
    end: float = Field(..., ge=0, description="End time in seconds (non-negative)")
    type: Literal["visual", "audio"] = Field(
        ..., description='Violation type: "visual" or "audio"'
    )
    category: str = Field(..., max_length=200, description="Violation category")
    severity: Literal["error", "warning"] = Field(
        ..., description='Severity level: "error" or "warning"'
    )
    description: str = Field(
        ..., max_length=1000, description="Description of the violation"
    )
    clip_url: str = Field(..., max_length=500, description="URL to the violation clip")

    @model_validator(mode="after")
    def validate_timestamps(self) -> "VideoViolation":
        """Reject video violations where start >= end (Requirement 9.6)."""
        if self.start >= self.end:
            raise ValueError(
                f"Invalid timestamp range: start ({self.start}) must be less than end ({self.end})"
            )
        return self


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REMIX OUTPUT SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TextChange(BaseModel):
    """A single text change made during remix."""

    original: str = Field(..., description="Original non-compliant phrase")
    replacement: str = Field(..., description="Compliant replacement phrase")
    reason: str = Field(..., description="Reason for the change")


class TextRemixOutput(BaseModel):
    """Output schema for text remix (Requirement 1.4).

    Contains the original text, compliant rewrite, and a list of changes made.
    """

    original_text: str = Field(..., description="The original input text")
    compliant_text: str = Field(..., description="The rewritten compliant text")
    changes: list[TextChange] = Field(
        default_factory=list,
        description="List of changes with original, replacement, and reason",
    )


class AudioRemixOutput(BaseModel):
    """Output schema for audio remix (Requirement 2.5).

    Contains the original transcript, corrected transcript, generated audio path,
    and the voice identifier used.
    """

    original_transcript: str = Field(..., description="Original audio transcript")
    compliant_transcript: str = Field(
        ..., description="Corrected compliant transcript"
    )
    audio_path: str = Field(..., description="Path to the generated audio file")
    voice_used: str = Field(..., description="Voice identifier used for TTS")


class ImageRemixOutput(BaseModel):
    """Output schema for image remix (Requirement 3.6).

    Contains the violations addressed, the edit prompt used, the remediation
    options available, and the path to the result image.
    """

    violations: list[ImageViolation] = Field(
        ..., description="Violations addressed in this remix"
    )
    edit_prompt: str = Field(..., description="Edit prompt used for remediation")
    options: list[Literal["edit", "regenerate"]] = Field(
        default=["edit", "regenerate"],
        description="Available remediation options",
    )
    result_image_path: str = Field(
        ..., description="Path to the generated result image"
    )
