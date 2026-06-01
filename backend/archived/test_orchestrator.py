"""Unit tests for the Remediation Orchestrator.

Tests violation separation, sorting, non-overlapping validation,
and the orchestration logic including error handling.
"""

from __future__ import annotations

import pytest

from backend.jusads_video_compliance.models import Violation
from backend.jusads_video_compliance.orchestrator import (
    _separate_violations,
    _validate_non_overlapping,
)


# --- Helper to create test violations ---


def _make_violation(
    start: float,
    end: float,
    vtype: str = "visual",
    category: str = "Sexual/Explicit",
    severity: str = "Severe",
) -> Violation:
    """Create a test Violation with minimal required fields."""
    return Violation(
        timestamp_start=start,
        timestamp_end=end,
        category=category,
        severity=severity,
        description="Test violation",
        violation_type=vtype,
        guideline_source="regulatory",
    )


# --- Tests for _separate_violations ---


class TestSeparateViolations:
    """Tests for violation separation and sorting logic."""

    def test_separates_visual_and_audio(self) -> None:
        """Visual and audio violations are separated into correct lists."""
        violations = [
            _make_violation(5.0, 10.0, "visual"),
            _make_violation(1.0, 3.0, "audio"),
            _make_violation(2.0, 4.0, "visual"),
            _make_violation(8.0, 12.0, "audio"),
        ]

        visual, audio = _separate_violations(violations)

        assert len(visual) == 2
        assert len(audio) == 2
        assert all(v.violation_type == "visual" for v in visual)
        assert all(v.violation_type == "audio" for v in audio)

    def test_sorts_by_timestamp_start_ascending(self) -> None:
        """Both categories are sorted by timestamp_start ascending."""
        violations = [
            _make_violation(10.0, 15.0, "visual"),
            _make_violation(2.0, 5.0, "visual"),
            _make_violation(7.0, 9.0, "visual"),
            _make_violation(20.0, 25.0, "audio"),
            _make_violation(1.0, 3.0, "audio"),
        ]

        visual, audio = _separate_violations(violations)

        assert [v.timestamp_start for v in visual] == [2.0, 7.0, 10.0]
        assert [v.timestamp_start for v in audio] == [1.0, 20.0]

    def test_empty_violations_list(self) -> None:
        """Empty input returns two empty lists."""
        visual, audio = _separate_violations([])
        assert visual == []
        assert audio == []

    def test_only_visual_violations(self) -> None:
        """When all violations are visual, audio list is empty."""
        violations = [
            _make_violation(1.0, 2.0, "visual"),
            _make_violation(3.0, 4.0, "visual"),
        ]

        visual, audio = _separate_violations(violations)

        assert len(visual) == 2
        assert len(audio) == 0

    def test_only_audio_violations(self) -> None:
        """When all violations are audio, visual list is empty."""
        violations = [
            _make_violation(1.0, 2.0, "audio"),
            _make_violation(3.0, 4.0, "audio"),
        ]

        visual, audio = _separate_violations(violations)

        assert len(visual) == 0
        assert len(audio) == 2


# --- Tests for _validate_non_overlapping ---


class TestValidateNonOverlapping:
    """Tests for non-overlapping visual segment validation."""

    def test_non_overlapping_returns_none(self) -> None:
        """Non-overlapping segments pass validation (return None)."""
        violations = [
            _make_violation(1.0, 3.0),
            _make_violation(3.0, 5.0),
            _make_violation(6.0, 8.0),
        ]
        assert _validate_non_overlapping(violations) is None

    def test_overlapping_returns_error_message(self) -> None:
        """Overlapping segments return an error message."""
        violations = [
            _make_violation(1.0, 5.0),
            _make_violation(4.0, 8.0),  # overlaps: 5.0 > 4.0
        ]
        result = _validate_non_overlapping(violations)
        assert result is not None
        assert "Overlapping" in result

    def test_single_violation_is_valid(self) -> None:
        """A single violation always passes validation."""
        violations = [_make_violation(1.0, 10.0)]
        assert _validate_non_overlapping(violations) is None

    def test_empty_list_is_valid(self) -> None:
        """An empty list always passes validation."""
        assert _validate_non_overlapping([]) is None

    def test_adjacent_segments_are_valid(self) -> None:
        """Segments where end == start of next are valid (not overlapping)."""
        violations = [
            _make_violation(0.0, 5.0),
            _make_violation(5.0, 10.0),
        ]
        assert _validate_non_overlapping(violations) is None

    def test_multiple_overlaps_reports_first(self) -> None:
        """When multiple overlaps exist, the first one is reported."""
        violations = [
            _make_violation(1.0, 6.0),
            _make_violation(4.0, 9.0),  # first overlap
            _make_violation(7.0, 12.0),  # second overlap
        ]
        result = _validate_non_overlapping(violations)
        assert result is not None
        assert "1.00s" in result and "6.00s" in result


# --- Tests for orchestrate_remediation (async) ---


class TestOrchestrateRemediation:
    """Tests for the main orchestration function."""

    @pytest.mark.asyncio
    async def test_rejects_overlapping_visual_violations(self) -> None:
        """Overlapping visual violations cause rejection with all failed."""
        from backend.jusads_video_compliance.orchestrator import (
            orchestrate_remediation,
        )

        violations = [
            _make_violation(1.0, 5.0, "visual"),
            _make_violation(4.0, 8.0, "visual"),  # overlaps
        ]

        result = await orchestrate_remediation(
            video_path="dummy.mp4",
            violations=violations,
            market="malaysia",
            ethnicity="malay",
            age_group="all_ages",
            language="ms",
            output_dir="test_output",
        )

        assert result.violations_fixed == 0
        assert result.violations_failed == len(violations)
        assert result.process_log == []

    @pytest.mark.asyncio
    async def test_empty_violations_produces_compose_only(self) -> None:
        """Empty violations list still composes (copies) the final video."""
        import tempfile
        import os
        from backend.jusads_video_compliance.orchestrator import (
            orchestrate_remediation,
        )

        # Create a temporary "video" file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = await orchestrate_remediation(
                    video_path=video_path,
                    violations=[],
                    market="malaysia",
                    ethnicity="malay",
                    age_group="all_ages",
                    language="ms",
                    output_dir=output_dir,
                )

                assert result.violations_fixed == 0
                assert result.violations_failed == 0
                # Should have compose_final entry
                assert len(result.process_log) == 1
                assert result.process_log[0].action == "compose_final"
                assert result.process_log[0].success is True
        finally:
            os.unlink(video_path)
