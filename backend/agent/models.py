"""
models.py
─────────
Pydantic models for compliance check persistence (Supabase).

These models represent the structured data stored in the compliance_checks
and violations tables. They are used for serialization/deserialization when
communicating with the Supabase client and the API layer.
"""

from datetime import datetime, timezone
from typing import Optional

import uuid
from pydantic import BaseModel, Field, field_validator


class CheckRecord(BaseModel):
    """A single compliance check record stored in the compliance_checks table.

    Maps to Supabase `compliance_checks` table columns defined in Requirement 8.1.
    """

    check_id: str
    user_id: str
    project_id: uuid.UUID
    media_type: str  # "text" | "image" | "audio" | "video"
    market: str
    ethnicity: str
    age_group: str
    risk_percentage: Optional[float] = None
    risk_band: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "pending"  # "pending" | "checked" | "verified" | "edit_pending" | "remediated" | "remix_failed"
    result_json: Optional[dict] = None
    s3_upload_key: Optional[str] = None
    s3_segmented_key: Optional[str] = None
    s3_remix_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ViolationRecord(BaseModel):
    """A single violation detected during a compliance check.

    Maps to Supabase `violations` table columns defined in Requirement 8.2.
    The (check_id, violation_index) pair is unique per the DB constraint.
    start_time and end_time are in seconds — used by the frontend for video seeking.
    """

    check_id: str
    violation_index: int
    type: str
    severity: str
    description: Optional[str] = None
    start_time: Optional[float] = None  # seconds
    end_time: Optional[float] = None  # seconds


class HistoryResponse(BaseModel):
    """Paginated response for compliance check history.

    Returned by the GET /api/compliance/history endpoint and the
    SupabaseComplianceStore.get_history() method.
    """

    records: list[CheckRecord]
    total: int
    page: int
    page_size: int


class TaskRecord(BaseModel):
    """A unified task row in the tasks table (Requirement 11.1).

    Represents both compliance and generation tasks. Compliance tasks store
    a reference_id pointing to compliance_checks.id; generation tasks store
    the pipeline graph state as JSONB in pipeline_state.
    """

    id: Optional[str] = None
    project_id: str
    type: str  # "compliance" | "generation"
    status: str
    summary: Optional[str] = None
    reference_id: Optional[str] = None
    pipeline_state: Optional[dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateTaskRequest(BaseModel):
    """Request body for POST /api/projects/{project_id}/tasks."""

    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate task type is one of the allowed values."""
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
        """Validate project name is non-empty and ≤255 characters."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty")
        if len(stripped) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        return stripped
