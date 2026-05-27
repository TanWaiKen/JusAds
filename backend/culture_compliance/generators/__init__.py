"""Hypothesis strategies for property-based testing of the content compliance pipeline.

This package provides reusable Hypothesis strategies (generators) for creating
random but valid instances of the pipeline's core data models:

- submissions: Strategies for ContentSubmission objects (with ethnicity/age_group)
- results: Strategies for ComplianceResult and related output models (with guideline_source)
- file_metadata: Strategies for image and video file metadata validation
- cultural_guidelines: Strategies for GuidelineEntry objects
- csv_rows: Strategies for valid and invalid CSV row data
"""

from .submissions import (
    content_submission_strategy,
    text_submission_strategy,
    image_submission_strategy,
    video_submission_strategy,
    ethnicity_strategy,
    age_group_strategy,
)
from .results import (
    compliance_result_strategy,
    processing_metadata_strategy,
    text_issue_location_strategy,
    image_issue_location_strategy,
    video_issue_location_strategy,
    pipeline_warning_strategy,
    guideline_source_strategy,
)
from .file_metadata import (
    valid_image_metadata_strategy,
    invalid_image_metadata_strategy,
    valid_video_metadata_strategy,
    invalid_video_metadata_strategy,
)
from .cultural_guidelines import (
    valid_guideline_entry_strategy,
    valid_guideline_entry_dict_strategy,
    invalid_guideline_entry_strategy,
    valid_market_strategy,
    valid_ethnicity_strategy,
    valid_age_group_strategy,
    valid_category_strategy,
    valid_severity_strategy,
    valid_guideline_text_strategy,
    invalid_guideline_text_strategy,
)
from .csv_rows import (
    valid_csv_row_strategy,
    invalid_csv_row_strategy,
    mixed_csv_content_strategy,
)

__all__ = [
    # Submissions
    "content_submission_strategy",
    "text_submission_strategy",
    "image_submission_strategy",
    "video_submission_strategy",
    "ethnicity_strategy",
    "age_group_strategy",
    # Results
    "compliance_result_strategy",
    "processing_metadata_strategy",
    "text_issue_location_strategy",
    "image_issue_location_strategy",
    "video_issue_location_strategy",
    "pipeline_warning_strategy",
    "guideline_source_strategy",
    # File metadata
    "valid_image_metadata_strategy",
    "invalid_image_metadata_strategy",
    "valid_video_metadata_strategy",
    "invalid_video_metadata_strategy",
    # Cultural guidelines
    "valid_guideline_entry_strategy",
    "valid_guideline_entry_dict_strategy",
    "invalid_guideline_entry_strategy",
    "valid_market_strategy",
    "valid_ethnicity_strategy",
    "valid_age_group_strategy",
    "valid_category_strategy",
    "valid_severity_strategy",
    "valid_guideline_text_strategy",
    "invalid_guideline_text_strategy",
    # CSV rows
    "valid_csv_row_strategy",
    "invalid_csv_row_strategy",
    "mixed_csv_content_strategy",
]
