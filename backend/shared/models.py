"""
models.py
─────────
Unified data models for the Langhub backend.

This module contains:
  1. Dataclasses that map 1:1 to each database table (projects, compliance_checks,
     violations, tasks).
  2. LangGraph pipeline state TypedDicts (Compliance_State, Remediation_State).
  3. Pydantic models for API request/response validation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TypedDict

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Remix redesign — Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class TriageOutcome(str, Enum):
    """Three-outcome triage result for the image remix pipeline."""
    COMPLIANT = "compliant"
    EDIT = "edit"
    CANNOT_FIX = "cannot_fix"


class EditMode(str, Enum):
    """Imagen 3.0 inpainting edit modes used by the AIDesigner."""
    INPAINT_INSERT = "INPAINT_INSERT"
    INPAINT_REMOVE = "INPAINT_REMOVE"


# ─────────────────────────────────────────────────────────────────────────────
# Remix redesign — TypedDicts (LangGraph state convention)
# ─────────────────────────────────────────────────────────────────────────────


class TriageResult(TypedDict):
    """Structured output from the TriageDecider."""
    outcome: str       # One of TriageOutcome values
    reasoning: str
    guidance: str      # Empty for COMPLIANT/EDIT, populated for CANNOT_FIX
    platform_ban: bool  # True if product type is banned on platform


class EditPlan(TypedDict):
    """Structured output from the AIDesigner — plan for how to edit an image."""
    mode: str              # One of EditMode values
    inpaint_prompt: str    # ≤ 60 words
    reasoning: str
    target_description: str


class BiasCheckResult(TypedDict):
    """Lightweight bias/hallucination check result."""
    passed: bool
    issues: list  # list[str] — empty if passed
    confidence: float  # 0.0–1.0


# ─────────────────────────────────────────────────────────────────────────────
# Table-mapped dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Project:
    """Maps to public.projects table.

    Columns:
      id            uuid  PK  (auto-generated)
      owner_email   text  NOT NULL
      name          text  NOT NULL  (max 255)
      description   text
      created_at    timestamptz  DEFAULT now()
      updated_at    timestamptz  DEFAULT now()
    """

    owner_email: str
    name: str
    description: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ComplianceCheck:
    """Maps to public.compliance_checks table.

    Columns:
      task_id          uuid  PK + FK -> tasks.id
      project_id       uuid  FK -> projects.id
      media_type       text  NOT NULL  ('text'|'image'|'audio'|'video')
      market           text  NOT NULL
      ethnicity        text  NOT NULL
      age_group        text  NOT NULL
      platform         text  NOT NULL  DEFAULT 'general'
      risk_percentage  numeric  (0–100)
      status           text  NOT NULL  ('pending'|'checked'|'verified'|'edit_pending'|'remediated'|'remix_failed')
      result_json      jsonb
      s3_upload_key    text
      s3_segmented_key text
      s3_remix_key     text
      created_at       timestamptz  DEFAULT now()
      updated_at       timestamptz  DEFAULT now()
    """

    task_id: str
    project_id: str
    media_type: str
    market: str
    ethnicity: str
    age_group: str
    platform: str = "general"
    risk_percentage: Optional[float] = None
    status: str = "pending"
    result_json: Optional[dict] = None
    s3_upload_key: Optional[str] = None
    s3_segmented_key: Optional[str] = None
    s3_remix_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Violation:
    """Maps to public.violations table.

    Columns:
      id               uuid  PK  (auto-generated)
      task_id          uuid  FK -> compliance_checks.task_id
      violation_index  integer  NOT NULL
      type             text  NOT NULL
      severity         text  NOT NULL
      description      text  (max 2000)
      start_time       numeric  (seconds)
      end_time         numeric  (seconds)
      clip_s3_key      text
      created_at       timestamptz  DEFAULT now()
    """

    task_id: str
    violation_index: int
    type: str
    severity: str
    description: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    clip_s3_key: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Task:
    """Maps to public.tasks table.

    Columns:
      id              uuid  PK  (auto-generated)
      project_id      uuid  FK -> projects.id
      type            text  NOT NULL  ('compliance'|'generation')
      status          text  NOT NULL
      summary         text
      pipeline_state  jsonb
      created_at      timestamptz  DEFAULT now()
      updated_at      timestamptz  DEFAULT now()
    """

    project_id: str
    type: str
    status: str
    summary: Optional[str] = None
    pipeline_state: Optional[dict] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline state TypedDicts (LangGraph graph state)
# ─────────────────────────────────────────────────────────────────────────────


class Compliance_State(TypedDict):
    """LangGraph state for the Compliance Pipeline.

    This is NOT a DB table — it is the state dict passed between pipeline nodes.
    Uses TypedDict per LangGraph conventions for proper state schema validation,
    channel merging, and checkpoint serialization.
    """

    session_id: str
    media_type: str              # "text" | "image" | "audio" | "video"
    input_path: str              # file path for media files
    text_input: str              # text content (for text media type)
    market: str                  # "malaysia" | "singapore"
    platform: str                # "tiktok" | "meta" | "instagram" | "youtube" | "shopee"
    ethnicity: str               # "malay" | "chinese" | "indian" | "all"
    age_group: str               # "gen_z" | "millennial" | "gen_x" | "all_ages"
    iteration: int
    result: dict
    status: str                  # "pending" | "checked" | "pass" | "critical_regen" | "remediate"
    user_prompt_context: str     # additional campaign/creative brief details (up to 2000 chars)
    task_id: str
    remediated_path: str
    remix_iteration: int


class Remediation_State(TypedDict):
    """LangGraph state for the Remediation Pipeline.

    Holds remediation context, strategy, and output paths. Communicated with
    the Compliance Pipeline only via the compliance_checks table.
    """

    task_id: str
    media_type: str              # "text" | "image" | "audio" | "video"
    source_media_url: str
    compliance_result: dict
    remediation_plan: dict
    platform_target: str
    aspect_ratio: str
    strategy: str
    remediated_paths: list
    status: str                  # "pending" | "remediating" | "remediated" | "remix_failed"


# Backward-compatible alias — deprecated, will be removed once pipeline.py
# and pipeline_runner.py are migrated to use Compliance_State (Tasks 5.1, 7.1).
@dataclass
class ComplianceState:
    """DEPRECATED: Use Compliance_State TypedDict instead.

    Retained temporarily for backward compatibility with pipeline.py and
    pipeline_runner.py until they are refactored in subsequent tasks.
    """

    session_id: str
    media_type: str
    input_path: str
    text_input: str
    market: str
    platform: str
    ethnicity: str
    age_group: str
    iteration: int = 0
    result: dict = field(default_factory=dict)
    status: str = "pending"
    user_prompt_context: str = ""
    task_id: str = ""
    remediated_path: str = ""
    remix_iteration: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models — API request/response validation
# ─────────────────────────────────────────────────────────────────────────────


class ComplianceOutput(BaseModel):
    """Unified compliance check output — same structure for ALL media types.

    Always has all fields. Fields that don't apply are null.
    This is what gets stored in compliance_checks.result_json AND sent via WebSocket.

    Example output:
    {
        "risk_percentage": 100,
        "risk_level": "Critical",
        "high_risk_indicator": ["Women shown in underwear", ...],
        "explanation": "...",
        "suggestion": "...",
        "localization_plan": "...",
        "violations_timeline": [...] or null,
        "segmentation": { "mask_path": "...", ... } or null,
        "verification": { "verified": [...], ... } or null,
        "evaluation": { "bias_detected": false, ... } or null,
        "remix": { "output_path": "...", ... } or null,
        "media_type": "image",
        "transcript": null
    }
    """

    # Core assessment (always present)
    risk_percentage: int = 0
    risk_level: str = "Low"  # Low | Moderate | High | Critical
    high_risk_indicator: list[str] = []
    explanation: str = ""
    suggestion: str = ""
    localization_plan: str = ""

    # Violations with location/timing (null for text-only)
    violations_timeline: Optional[list[dict]] = None

    # Segmentation result (image/video only)
    segmentation: Optional[dict] = None

    # Verification against regulatory sources
    verification: Optional[dict] = None

    # Bias & hallucination evaluation
    evaluation: Optional[dict] = None

    # Remix/remediation result (after edit_image, rewrite_text, etc.)
    remix: Optional[dict] = None

    # Media-specific metadata
    media_type: str = ""
    transcript: Optional[dict] = None  # audio/video only

    @classmethod
    def from_pipeline_result(cls, result: dict, media_type: str = "") -> "ComplianceOutput":
        """Build ComplianceOutput from raw pipeline state.result dict.

        Guarantees all fields are present even if nodes were skipped or failed.
        """
        return cls(
            risk_percentage=result.get("risk_percentage", 0),
            risk_level=result.get("risk_level", "Low"),
            high_risk_indicator=result.get("high_risk_indicator", []),
            explanation=result.get("explanation", ""),
            suggestion=result.get("suggestion", ""),
            localization_plan=result.get("localization_plan", ""),
            violations_timeline=result.get("violations_timeline"),
            segmentation=result.get("segmentation"),
            verification=result.get("verification"),
            evaluation=result.get("evaluation"),
            remix=result.get("remix"),
            media_type=media_type or result.get("media_type", ""),
            transcript=result.get("_transcript") or result.get("transcript"),
        )


class CheckRecord(BaseModel):
    """Pydantic model for serialization of a compliance_checks row.

    Used by the Supabase client and API layer for JSON (de)serialization.
    """

    task_id: uuid.UUID
    project_id: uuid.UUID
    media_type: str
    market: str
    ethnicity: str
    age_group: str
    platform: str = "general"
    risk_percentage: Optional[float] = None
    status: str = "pending"
    result_json: Optional[dict] = None
    s3_upload_key: Optional[str] = None
    s3_segmented_key: Optional[str] = None
    s3_remix_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ViolationRecord(BaseModel):
    """Pydantic model for serialization of a violations row."""

    task_id: uuid.UUID
    violation_index: int
    type: str
    severity: str
    description: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class HistoryResponse(BaseModel):
    """Paginated response for compliance check history."""

    records: list[CheckRecord]
    total: int
    page: int
    page_size: int


class TaskRecord(BaseModel):
    """Pydantic model for serialization of a tasks row."""

    id: Optional[str] = None
    project_id: str
    type: str
    status: str
    summary: Optional[str] = None
    pipeline_state: Optional[dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateTaskRequest(BaseModel):
    """Request body for POST /api/projects/{project_id}/tasks."""

    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid = {"compliance", "generation"}
        if v not in valid:
            raise ValueError(f"type must be one of: {', '.join(sorted(valid))}")
        return v


class UpdatePipelineRequest(BaseModel):
    """Request body for PUT /api/projects/{project_id}/tasks/{task_id}/pipeline."""

    status: str
    pipeline_state: dict


class UpdateProjectRequest(BaseModel):
    """Request body for PATCH /api/projects/{project_id}."""

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty")
        if len(stripped) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        return stripped
