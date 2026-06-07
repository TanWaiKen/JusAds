"""Unit tests for the Image Remixer module.

Tests core logic including empty violations handling, violation parsing,
prompt construction, and error handling — all without requiring actual API calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from jusads_remix_pipeline.image_remixer import (
    remix_image,
    _parse_violations,
    _build_combined_edit_prompt,
    _build_inpainting_prompt,
    _build_regeneration_prompt,
    _get_mime_type,
    _mime_to_extension,
)
from jusads_remix_pipeline.models import ImageRemixOutput, ImageViolation


# ─── Test: Empty violations (Requirement 3.8) ─────────────────────────────────


class TestEmptyViolations:
    """Requirement 3.8: Empty violations → skip generation, return original."""

    def test_empty_violations_returns_original_path(self):
        result = remix_image(
            image_path="/path/to/image.png",
            violations=[],
            target_audience={"market": "Malaysia", "ethnicity": "Malay"},
            option="edit",
        )
        assert result.result_image_path == "/path/to/image.png"

    def test_empty_violations_returns_empty_violations_list(self):
        result = remix_image(
            image_path="/some/image.jpg",
            violations=[],
            target_audience={"market": "Malaysia", "ethnicity": "Chinese"},
            option="regenerate",
        )
        assert result.violations == []
        assert result.edit_prompt == ""

    def test_empty_violations_has_both_options(self):
        result = remix_image(
            image_path="/img.png",
            violations=[],
            target_audience={},
            option="edit",
        )
        assert result.options == ["edit", "regenerate"]


# ─── Test: Violation Parsing ───────────────────────────────────────────────────


class TestParseViolations:
    """Test violation dict parsing into ImageViolation models."""

    def test_parse_valid_violation(self):
        violations = [
            {
                "index": 0,
                "type": "visual",
                "component": "Female model attire",
                "severity": "error",
                "location_description": "Center of image, main model",
                "edit_prompt": "Replace sleeveless top with long-sleeved blouse",
            }
        ]
        result = _parse_violations(violations)
        assert len(result) == 1
        assert result[0].component == "Female model attire"
        assert result[0].severity == "error"
        assert result[0].edit_prompt == "Replace sleeveless top with long-sleeved blouse"

    def test_parse_multiple_violations(self):
        violations = [
            {
                "index": 0,
                "type": "visual",
                "component": "Attire",
                "severity": "error",
                "location_description": "Left model",
                "edit_prompt": "Add hijab",
            },
            {
                "index": 1,
                "type": "visual",
                "component": "Skin exposure",
                "severity": "warning",
                "location_description": "Right model arms",
                "edit_prompt": "Cover exposed arms with long sleeves",
            },
        ]
        result = _parse_violations(violations)
        assert len(result) == 2

    def test_parse_handles_missing_fields_gracefully(self):
        violations = [{"component": "Something", "edit_prompt": "Fix it"}]
        result = _parse_violations(violations)
        assert len(result) == 1
        assert result[0].index == 0
        assert result[0].type == "visual"
        assert result[0].severity == "error"


# ─── Test: Edit Prompt Building ────────────────────────────────────────────────


class TestBuildCombinedEditPrompt:
    """Test combining edit prompts from multiple violations."""

    def test_single_violation_prompt(self):
        violations = [
            {"component": "Hair", "edit_prompt": "Add hijab to female model"}
        ]
        result = _build_combined_edit_prompt(violations)
        assert "Hair" in result
        assert "Add hijab to female model" in result

    def test_multiple_violations_combined(self):
        violations = [
            {"component": "Hair", "edit_prompt": "Add hijab"},
            {"component": "Arms", "edit_prompt": "Cover arms with long sleeves"},
        ]
        result = _build_combined_edit_prompt(violations)
        assert "Add hijab" in result
        assert "Cover arms with long sleeves" in result

    def test_empty_edit_prompt_skipped(self):
        violations = [
            {"component": "Hair", "edit_prompt": ""},
            {"component": "Arms", "edit_prompt": "Cover arms"},
        ]
        result = _build_combined_edit_prompt(violations)
        assert "Hair" not in result
        assert "Cover arms" in result


# ─── Test: Inpainting Prompt ──────────────────────────────────────────────────


class TestBuildInpaintingPrompt:
    """Test inpainting prompt construction."""

    def test_includes_edit_instructions(self):
        prompt = _build_inpainting_prompt("Add hijab to model", "")
        assert "Add hijab to model" in prompt
        assert "Preserve" in prompt

    def test_includes_cultural_rules_when_provided(self):
        cultural = "Use ONLY Malay models/characters. All female models MUST wear hijab."
        prompt = _build_inpainting_prompt("Fix attire", cultural)
        assert "Malay models" in prompt
        assert "hijab" in prompt

    def test_no_cultural_section_when_empty(self):
        prompt = _build_inpainting_prompt("Fix attire", "")
        assert "CULTURAL RULES" not in prompt


# ─── Test: Regeneration Prompt ─────────────────────────────────────────────────


class TestBuildRegenerationPrompt:
    """Test regeneration prompt construction."""

    def test_includes_violations_summary(self):
        violations = [
            {"component": "Attire", "edit_prompt": "Make modest"},
        ]
        prompt = _build_regeneration_prompt(violations, "", {"market": "Malaysia"})
        assert "Attire" in prompt
        assert "Make modest" in prompt

    def test_includes_cultural_rules(self):
        cultural = "Use ONLY Chinese models/characters."
        prompt = _build_regeneration_prompt(
            [{"component": "Model"}], cultural, {"market": "Malaysia", "ethnicity": "Chinese"}
        )
        assert "Chinese models" in prompt

    def test_includes_market_info(self):
        prompt = _build_regeneration_prompt(
            [{"component": "X"}], "", {"market": "Singapore", "ethnicity": "Chinese"}
        )
        assert "Singapore" in prompt


# ─── Test: MIME Type Utilities ─────────────────────────────────────────────────


class TestMimeUtilities:
    """Test MIME type detection and conversion."""

    def test_png_mime_type(self):
        assert _get_mime_type("/path/to/image.png") == "image/png"

    def test_jpg_mime_type(self):
        assert _get_mime_type("/path/to/photo.jpg") == "image/jpeg"

    def test_jpeg_mime_type(self):
        assert _get_mime_type("/path/to/photo.jpeg") == "image/jpeg"

    def test_webp_mime_type(self):
        assert _get_mime_type("/path/to/img.webp") == "image/webp"

    def test_unknown_defaults_to_png(self):
        assert _get_mime_type("/path/to/file.bmp") == "image/png"

    def test_mime_to_extension_png(self):
        assert _mime_to_extension("image/png") == ".png"

    def test_mime_to_extension_jpeg(self):
        assert _mime_to_extension("image/jpeg") == ".jpg"

    def test_mime_to_extension_unknown(self):
        assert _mime_to_extension("image/tiff") == ".png"


# ─── Test: Error Handling (Requirement 3.7) ────────────────────────────────────


class TestErrorHandling:
    """Requirement 3.7: API error → return error preserving violations and edit prompt."""

    @patch("jusads_remix_pipeline.image_remixer._edit_image")
    def test_api_error_preserves_violations(self, mock_edit):
        mock_edit.side_effect = RuntimeError("Content filter blocked request")

        violations = [
            {
                "index": 0,
                "type": "visual",
                "component": "Attire",
                "severity": "error",
                "location_description": "Main model",
                "edit_prompt": "Add modest clothing",
            }
        ]

        result = remix_image(
            image_path="/original.png",
            violations=violations,
            target_audience={"market": "Malaysia", "ethnicity": "Malay"},
            option="edit",
        )

        # Should preserve violations
        assert len(result.violations) == 1
        assert result.violations[0].component == "Attire"
        # Should preserve edit prompt
        assert "Add modest clothing" in result.edit_prompt
        # Should return original image path on failure
        assert result.result_image_path == "/original.png"

    @patch("jusads_remix_pipeline.image_remixer._regenerate_image")
    def test_regenerate_error_preserves_data(self, mock_regen):
        mock_regen.side_effect = Exception("API timeout")

        violations = [
            {
                "index": 0,
                "type": "visual",
                "component": "Model ethnicity",
                "severity": "error",
                "location_description": "All models",
                "edit_prompt": "Use Chinese models only",
            }
        ]

        result = remix_image(
            image_path="/ad.jpg",
            violations=violations,
            target_audience={"market": "Malaysia", "ethnicity": "Chinese"},
            option="regenerate",
        )

        assert len(result.violations) == 1
        assert result.edit_prompt != ""
        assert result.result_image_path == "/ad.jpg"
        assert result.options == ["edit", "regenerate"]


# ─── Test: Options Always Present (Requirement 3.1) ────────────────────────────


class TestOptionsPresent:
    """Requirement 3.1: Always present exactly two options."""

    def test_options_on_empty_violations(self):
        result = remix_image("/img.png", [], {}, "edit")
        assert result.options == ["edit", "regenerate"]

    @patch("jusads_remix_pipeline.image_remixer._edit_image")
    def test_options_on_edit_success(self, mock_edit):
        mock_edit.return_value = "/result.png"

        result = remix_image(
            "/img.png",
            [{"index": 0, "type": "visual", "component": "X", "severity": "error",
              "location_description": "Y", "edit_prompt": "Fix"}],
            {"ethnicity": "Malay"},
            "edit",
        )
        assert result.options == ["edit", "regenerate"]
