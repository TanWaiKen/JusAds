"""Tests for the Video Composer module.

Tests the compose_video function and its internal helpers for timeline building,
segment stitching, and audio layering logic.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from jusads_remix_pipeline.video_composer import (
    _build_timeline,
    _get_media_duration,
    compose_video,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def sample_segment_plan():
    """A segment plan with two non-compliant chunks."""
    return [
        {
            "start_time": 3.0,
            "end_time": 8.0,
            "source_violation_index": 0,
            "chunk_sequence_number": 0,
            "is_short_form": True,
        },
        {
            "start_time": 12.0,
            "end_time": 18.0,
            "source_violation_index": 1,
            "chunk_sequence_number": 0,
            "is_short_form": False,
        },
    ]


@pytest.fixture
def sample_voiceover_segments():
    """Sample voiceover segments with timing."""
    return [
        {
            "audio_path": "/tmp/vo_segment_0.mp3",
            "start_time": 3.0,
            "end_time": 6.0,
            "duration": 3.0,
        },
        {
            "audio_path": "/tmp/vo_segment_1.mp3",
            "start_time": 12.0,
            "end_time": 16.0,
            "duration": 4.0,
        },
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TESTS: _build_timeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBuildTimeline:
    """Tests for the _build_timeline helper function."""

    def test_empty_plan_returns_single_original_segment(self):
        """When no segments are in the plan, the full video is original."""
        timeline, unavailable = _build_timeline([], [], 30.0)

        assert len(timeline) == 1
        assert timeline[0]["type"] == "original"
        assert timeline[0]["start_time"] == 0.0
        assert timeline[0]["end_time"] == 30.0
        assert unavailable == []

    def test_single_remixed_clip_with_surrounding_original(self, tmp_path):
        """A single remixed clip should be surrounded by original sections."""
        # Create a fake remixed video file
        fake_clip = tmp_path / "clip.mp4"
        fake_clip.write_text("fake")

        segment_plan = [
            {
                "start_time": 5.0,
                "end_time": 10.0,
                "source_violation_index": 0,
                "chunk_sequence_number": 0,
                "is_short_form": True,
            }
        ]
        remixed_clips = [
            {
                "video_path": str(fake_clip),
                "ambient_audio_path": "",
                "duration": 5.0,
                "start_time": 5.0,
                "end_time": 10.0,
            }
        ]

        timeline, unavailable = _build_timeline(segment_plan, remixed_clips, 20.0)

        # Expect: [0-5 original], [5-10 remixed], [10-20 original]
        assert len(timeline) == 3
        assert timeline[0]["type"] == "original"
        assert timeline[0]["start_time"] == 0.0
        assert timeline[0]["end_time"] == 5.0
        assert timeline[1]["type"] == "remixed"
        assert timeline[1]["start_time"] == 5.0
        assert timeline[1]["end_time"] == 10.0
        assert timeline[2]["type"] == "original"
        assert timeline[2]["start_time"] == 10.0
        assert timeline[2]["end_time"] == 20.0
        assert unavailable == []

    def test_unavailable_clip_flags_segment(self):
        """When a remixed clip file is missing, flag it as unavailable (Req 8.5)."""
        segment_plan = [
            {
                "start_time": 3.0,
                "end_time": 8.0,
                "source_violation_index": 0,
                "chunk_sequence_number": 0,
                "is_short_form": True,
            }
        ]
        # Clip with non-existent path
        remixed_clips = [
            {
                "video_path": "/nonexistent/clip.mp4",
                "ambient_audio_path": "",
                "duration": 5.0,
                "start_time": 3.0,
                "end_time": 8.0,
            }
        ]

        timeline, unavailable = _build_timeline(segment_plan, remixed_clips, 20.0)

        # Should be flagged as unavailable
        assert len(unavailable) == 1
        assert unavailable[0]["start_time"] == 3.0
        assert unavailable[0]["end_time"] == 8.0
        assert "reason" in unavailable[0]

        # Timeline should still have the segment as "original" fallback
        remixed_count = sum(1 for s in timeline if s["type"] == "remixed")
        assert remixed_count == 0

    def test_no_gaps_or_overlaps_in_timeline(self, tmp_path):
        """Timeline should cover the full duration with no gaps or overlaps (Req 8.1)."""
        fake_clip_1 = tmp_path / "clip1.mp4"
        fake_clip_1.write_text("fake")
        fake_clip_2 = tmp_path / "clip2.mp4"
        fake_clip_2.write_text("fake")

        segment_plan = [
            {"start_time": 2.0, "end_time": 5.0, "source_violation_index": 0, "chunk_sequence_number": 0, "is_short_form": True},
            {"start_time": 10.0, "end_time": 15.0, "source_violation_index": 1, "chunk_sequence_number": 0, "is_short_form": True},
        ]
        remixed_clips = [
            {"video_path": str(fake_clip_1), "ambient_audio_path": "", "duration": 3.0, "start_time": 2.0, "end_time": 5.0},
            {"video_path": str(fake_clip_2), "ambient_audio_path": "", "duration": 5.0, "start_time": 10.0, "end_time": 15.0},
        ]

        timeline, _ = _build_timeline(segment_plan, remixed_clips, 25.0)

        # Check no gaps: each segment's start should equal previous segment's end
        for i in range(1, len(timeline)):
            assert timeline[i]["start_time"] == timeline[i - 1]["end_time"], (
                f"Gap between timeline segments {i-1} and {i}"
            )

        # Check full coverage
        assert timeline[0]["start_time"] == 0.0
        assert timeline[-1]["end_time"] == 25.0

    def test_segment_at_video_start(self, tmp_path):
        """When a non-compliant segment starts at 0, no leading original section."""
        fake_clip = tmp_path / "clip.mp4"
        fake_clip.write_text("fake")

        segment_plan = [
            {"start_time": 0.0, "end_time": 5.0, "source_violation_index": 0, "chunk_sequence_number": 0, "is_short_form": True},
        ]
        remixed_clips = [
            {"video_path": str(fake_clip), "ambient_audio_path": "", "duration": 5.0, "start_time": 0.0, "end_time": 5.0},
        ]

        timeline, _ = _build_timeline(segment_plan, remixed_clips, 20.0)

        assert timeline[0]["type"] == "remixed"
        assert timeline[0]["start_time"] == 0.0
        assert timeline[0]["end_time"] == 5.0

    def test_segment_at_video_end(self, tmp_path):
        """When a non-compliant segment ends at video end, no trailing original section."""
        fake_clip = tmp_path / "clip.mp4"
        fake_clip.write_text("fake")

        segment_plan = [
            {"start_time": 15.0, "end_time": 20.0, "source_violation_index": 0, "chunk_sequence_number": 0, "is_short_form": True},
        ]
        remixed_clips = [
            {"video_path": str(fake_clip), "ambient_audio_path": "", "duration": 5.0, "start_time": 15.0, "end_time": 20.0},
        ]

        timeline, _ = _build_timeline(segment_plan, remixed_clips, 20.0)

        assert timeline[-1]["type"] == "remixed"
        assert timeline[-1]["end_time"] == 20.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TESTS: compose_video (integration-level with mocked FFmpeg)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestComposeVideo:
    """Tests for the compose_video public function."""

    def test_missing_original_video_returns_error(self):
        """compose_video should error when original video path is invalid."""
        result = compose_video(
            segment_plan=[],
            remixed_clips=[],
            voiceover_segments=[],
            original_video_path="/nonexistent/video.mp4",
        )

        assert result["error"] is not None
        assert "not found" in result["error"]
        assert result["video_path"] == ""
        assert result["duration"] == 0.0

    def test_empty_original_video_path_returns_error(self):
        """compose_video should error when original video path is empty."""
        result = compose_video(
            segment_plan=[],
            remixed_clips=[],
            voiceover_segments=[],
            original_video_path="",
        )

        assert result["error"] is not None
        assert result["video_path"] == ""

    @patch("jusads_remix_pipeline.video_composer._get_media_duration")
    def test_zero_duration_original_returns_error(self, mock_duration, tmp_path):
        """compose_video should error if original video duration is 0."""
        fake_video = tmp_path / "video.mp4"
        fake_video.write_text("fake")
        mock_duration.return_value = 0.0

        result = compose_video(
            segment_plan=[],
            remixed_clips=[],
            voiceover_segments=[],
            original_video_path=str(fake_video),
        )

        assert result["error"] is not None
        assert "duration" in result["error"].lower()

    def test_return_format_has_required_fields(self):
        """The return dict should always contain the expected keys."""
        result = compose_video(
            segment_plan=[],
            remixed_clips=[],
            voiceover_segments=[],
            original_video_path="/nonexistent/video.mp4",
        )

        assert "video_path" in result
        assert "duration" in result
        assert "unavailable_segments" in result
        assert "error" in result

    @patch("jusads_remix_pipeline.video_composer._get_media_duration")
    @patch("jusads_remix_pipeline.video_composer._layer_audio")
    @patch("jusads_remix_pipeline.video_composer._stitch_video_segments")
    def test_unavailable_clips_are_flagged(
        self, mock_stitch, mock_layer, mock_duration, tmp_path
    ):
        """Unavailable clips should be flagged in the output (Req 8.5)."""
        fake_video = tmp_path / "video.mp4"
        fake_video.write_text("fake")
        fake_stitched = tmp_path / "stitched.mp4"
        fake_stitched.write_text("fake")
        fake_final = tmp_path / "final.mp4"
        fake_final.write_text("fake")

        mock_duration.return_value = 30.0
        mock_stitch.return_value = str(fake_stitched)
        mock_layer.return_value = str(fake_final)

        segment_plan = [
            {"start_time": 5.0, "end_time": 10.0, "source_violation_index": 0, "chunk_sequence_number": 0, "is_short_form": True},
        ]
        # Clip path doesn't exist
        remixed_clips = [
            {"video_path": "/missing/clip.mp4", "ambient_audio_path": "", "duration": 5.0, "start_time": 5.0, "end_time": 10.0},
        ]

        result = compose_video(
            segment_plan=segment_plan,
            remixed_clips=remixed_clips,
            voiceover_segments=[],
            original_video_path=str(fake_video),
        )

        assert len(result["unavailable_segments"]) == 1
        assert result["unavailable_segments"][0]["start_time"] == 5.0
        assert result["unavailable_segments"][0]["end_time"] == 10.0
        assert "reason" in result["unavailable_segments"][0]
