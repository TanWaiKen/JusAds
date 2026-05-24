"""Property-based tests for video pipeline validation.

Feature: content-compliance
Tests Properties 8, 9, and 10 from the design document.

**Validates: Requirements 4.1, 4.4, 4.6, 4.7**
"""

import os
import tempfile
from math import ceil
from unittest.mock import patch

from hypothesis import given, settings, assume, strategies as st

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step2_video_analysis import (
    MAX_VIDEO_SIZE_BYTES,
    MAX_DURATION_SECONDS,
    SUPPORTED_EXTENSIONS,
    _merge_chronologically,
    video_processing,
)
from culture_compliance.services.frame_extractor import (
    extract_frames,
    MIN_INTERVAL,
    MAX_INTERVAL,
)


# --- Strategies ---


@st.composite
def valid_video_duration_and_interval(draw):
    """Generate valid video duration and frame interval pairs.

    Duration: positive float (0.1 to 300 seconds)
    Interval: between 0.5 and 5.0 seconds
    """
    duration = draw(st.floats(min_value=0.1, max_value=300.0, allow_nan=False, allow_infinity=False))
    interval = draw(st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False))
    return (duration, interval)


@st.composite
def timestamped_frame_descriptions(draw):
    """Generate a list of timestamped frame descriptions."""
    n = draw(st.integers(min_value=0, max_value=20))
    frames = []
    for _ in range(n):
        timestamp = draw(st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False))
        description = draw(st.text(min_size=1, max_size=100).filter(lambda s: s.strip()))
        frames.append({"timestamp": timestamp, "description": description})
    return frames


@st.composite
def timestamped_transcript_segments(draw):
    """Generate a list of timestamped transcript segments."""
    n = draw(st.integers(min_value=0, max_value=20))
    segments = []
    for _ in range(n):
        start_time = draw(st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False))
        end_time = draw(st.floats(min_value=start_time, max_value=start_time + 30.0, allow_nan=False, allow_infinity=False))
        text = draw(st.text(min_size=1, max_size=100).filter(lambda s: s.strip()))
        segments.append({"start_time": start_time, "end_time": end_time, "text": text})
    return segments


@st.composite
def valid_video_metadata(draw):
    """Generate valid video file metadata that should be accepted.

    Valid means: format in {MP4, MOV, WebM}, size <= 100MB, duration <= 300s.
    """
    fmt = draw(st.sampled_from([".mp4", ".mov", ".webm"]))
    size_bytes = draw(st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES))
    duration_seconds = draw(st.floats(min_value=0.1, max_value=MAX_DURATION_SECONDS, allow_nan=False, allow_infinity=False))
    return (fmt, size_bytes, duration_seconds)


@st.composite
def invalid_format_video_metadata(draw):
    """Generate video metadata with unsupported format."""
    fmt = draw(st.sampled_from([".avi", ".mkv", ".flv", ".wmv", ".3gp", ".ts", ".gif"]))
    size_bytes = draw(st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES))
    duration_seconds = draw(st.floats(min_value=0.1, max_value=MAX_DURATION_SECONDS, allow_nan=False, allow_infinity=False))
    return (fmt, size_bytes, duration_seconds)


@st.composite
def oversized_video_metadata(draw):
    """Generate video metadata that exceeds 100MB size limit."""
    fmt = draw(st.sampled_from([".mp4", ".mov", ".webm"]))
    size_bytes = draw(st.integers(min_value=MAX_VIDEO_SIZE_BYTES + 1, max_value=MAX_VIDEO_SIZE_BYTES * 3))
    duration_seconds = draw(st.floats(min_value=0.1, max_value=MAX_DURATION_SECONDS, allow_nan=False, allow_infinity=False))
    return (fmt, size_bytes, duration_seconds)


@st.composite
def over_duration_video_metadata(draw):
    """Generate video metadata that exceeds 300s duration limit."""
    fmt = draw(st.sampled_from([".mp4", ".mov", ".webm"]))
    size_bytes = draw(st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES))
    duration_seconds = draw(st.floats(min_value=MAX_DURATION_SECONDS + 0.1, max_value=3600.0, allow_nan=False, allow_infinity=False))
    return (fmt, size_bytes, duration_seconds)


# --- Helper functions ---


def _create_video_pipeline_state(video_path: str) -> PipelineState:
    """Create a PipelineState with a video file path."""
    submission = ContentSubmission(
        content=video_path,
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
    )


# --- Property 8: Video Frame Count Calculation ---
# **Validates: Requirements 4.1**


@settings(max_examples=100, deadline=5000)
@given(data=valid_video_duration_and_interval())
def test_property_8_frame_count_matches_ceil_formula(data):
    """Property 8: Video Frame Count Calculation.

    For any video duration (in seconds) and frame interval (between 0.5 and 5.0
    seconds), the frame extractor SHALL produce exactly `ceil(duration / interval)`
    frames, each associated with a timestamp that is a multiple of the interval
    starting from 0.

    **Validates: Requirements 4.1**
    """
    duration, interval = data

    expected_frame_count = ceil(duration / interval)

    # Mock _get_video_duration to return our generated duration
    # Mock _extract_single_frame to return dummy frame bytes
    with patch(
        "culture_compliance.services.frame_extractor._get_video_duration",
        return_value=duration,
    ), patch(
        "culture_compliance.services.frame_extractor._extract_single_frame",
        return_value=b"\xff\xd8\xff\xe0fake_jpeg_data\xff\xd9",
    ):
        frames = extract_frames("fake_video.mp4", interval=interval)

    # Verify frame count matches ceil(duration / interval)
    assert len(frames) == expected_frame_count, (
        f"Expected {expected_frame_count} frames for duration={duration}s, "
        f"interval={interval}s, but got {len(frames)}"
    )

    # Verify each frame timestamp is a multiple of interval starting from 0
    for i, frame in enumerate(frames):
        expected_timestamp = i * interval
        assert frame["timestamp"] == expected_timestamp, (
            f"Frame {i} timestamp should be {expected_timestamp}, "
            f"but got {frame['timestamp']}"
        )


# --- Property 9: Chronological Merge Ordering ---
# **Validates: Requirements 4.4**


@settings(max_examples=100, deadline=5000)
@given(
    frame_descriptions=timestamped_frame_descriptions(),
    transcript_segments=timestamped_transcript_segments(),
)
def test_property_9_chronological_merge_ordering(frame_descriptions, transcript_segments):
    """Property 9: Chronological Merge Ordering.

    For any set of timestamped frame descriptions and transcript segments, the
    unified content description produced by the video pipeline SHALL order all
    entries by timestamp in non-decreasing order.

    **Validates: Requirements 4.4**
    """
    # Skip if both inputs are empty (no entries to order)
    assume(len(frame_descriptions) > 0 or len(transcript_segments) > 0)

    result = _merge_chronologically(frame_descriptions, transcript_segments)

    # The result should be a string with entries separated by newlines
    lines = result.strip().split("\n") if result.strip() else []

    # Extract timestamps from the formatted output
    # Format is: [MM:SS] [Visual|Audio] description
    timestamps = []
    for line in lines:
        if line.startswith("["):
            # Parse MM:SS timestamp
            ts_str = line.split("]")[0].lstrip("[")
            parts = ts_str.split(":")
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                timestamps.append(minutes * 60 + seconds)

    # Verify non-decreasing order
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1], (
            f"Timestamps not in non-decreasing order: "
            f"timestamp[{i-1}]={timestamps[i-1]} > timestamp[{i}]={timestamps[i]}\n"
            f"Full output:\n{result}"
        )


# --- Property 10: Video File Validation ---
# **Validates: Requirements 4.6, 4.7**


@settings(max_examples=100, deadline=5000)
@given(metadata=valid_video_metadata())
def test_property_10_valid_videos_accepted(metadata):
    """Property 10: Video File Validation - valid videos are accepted.

    For any video file metadata (format, size_bytes, duration_seconds), the video
    pipeline SHALL accept the file if and only if: format is in {MP4, MOV, WebM}
    AND size_bytes <= 104,857,600 AND duration_seconds <= 300.

    This test verifies the acceptance case.

    **Validates: Requirements 4.6, 4.7**
    """
    fmt, size_bytes, duration_seconds = metadata

    # Create a temporary file with the correct extension
    with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
        tmp_path = tmp.name
        # Write minimal content
        tmp.write(b"\x00" * 100)

    try:
        state = _create_video_pipeline_state(tmp_path)

        # Mock file system and processing operations
        with patch(
            "culture_compliance.nodes.step2_video_analysis._detect_video_format_by_extension",
            return_value=fmt,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._get_file_size",
            return_value=size_bytes,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._get_video_duration",
            return_value=duration_seconds,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus",
            return_value="Video analysis result from Pegasus",
        ), patch(
            "os.path.exists",
            return_value=True,
        ):
            result_state = video_processing(state)

        # Valid videos should NOT produce validation errors
        validation_errors = [
            e for e in result_state.errors if e.get("error_type") == "validation"
        ]
        assert len(validation_errors) == 0, (
            f"Valid video (format={fmt}, size={size_bytes}, duration={duration_seconds}) "
            f"was rejected with errors: {validation_errors}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@settings(max_examples=100, deadline=5000)
@given(metadata=invalid_format_video_metadata())
def test_property_10_invalid_format_rejected(metadata):
    """Property 10: Video File Validation - invalid formats are rejected.

    For any video file with format NOT in {MP4, MOV, WebM}, the video pipeline
    SHALL reject the file with an appropriate error message.

    **Validates: Requirements 4.6**
    """
    fmt, size_bytes, duration_seconds = metadata

    # Create a temporary file with the invalid extension
    with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"\x00" * 100)

    try:
        state = _create_video_pipeline_state(tmp_path)

        # Mock format detection to return None (unsupported)
        with patch(
            "culture_compliance.nodes.step2_video_analysis._detect_video_format_by_extension",
            return_value=None,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._detect_video_format_by_magic",
            return_value=None,
        ), patch(
            "os.path.exists",
            return_value=True,
        ):
            result_state = video_processing(state)

        # Invalid format should produce a validation error
        validation_errors = [
            e for e in result_state.errors if e.get("error_type") == "validation"
        ]
        assert len(validation_errors) > 0, (
            f"Invalid format video (format={fmt}) was not rejected"
        )

        # Error message should mention format
        error_msg = validation_errors[0]["message"].lower()
        assert "format" in error_msg or "supported" in error_msg, (
            f"Error message does not mention format: {validation_errors[0]['message']}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@settings(max_examples=100, deadline=5000)
@given(metadata=oversized_video_metadata())
def test_property_10_oversized_videos_rejected(metadata):
    """Property 10: Video File Validation - oversized videos are rejected.

    For any video file with size_bytes > 104,857,600, the video pipeline SHALL
    reject the file with an appropriate error message.

    **Validates: Requirements 4.7**
    """
    fmt, size_bytes, duration_seconds = metadata

    # Create a temporary file with valid extension
    with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"\x00" * 100)

    try:
        state = _create_video_pipeline_state(tmp_path)

        # Mock format detection to pass, but size exceeds limit
        with patch(
            "culture_compliance.nodes.step2_video_analysis._detect_video_format_by_extension",
            return_value=fmt,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._get_file_size",
            return_value=size_bytes,
        ), patch(
            "os.path.exists",
            return_value=True,
        ):
            result_state = video_processing(state)

        # Oversized videos should produce a validation error
        validation_errors = [
            e for e in result_state.errors if e.get("error_type") == "validation"
        ]
        assert len(validation_errors) > 0, (
            f"Oversized video ({size_bytes} bytes) was not rejected"
        )

        # Error message should mention size
        error_msg = validation_errors[0]["message"].lower()
        assert "size" in error_msg or "mb" in error_msg or "bytes" in error_msg, (
            f"Error message does not mention size: {validation_errors[0]['message']}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@settings(max_examples=100, deadline=5000)
@given(metadata=over_duration_video_metadata())
def test_property_10_over_duration_videos_rejected(metadata):
    """Property 10: Video File Validation - over-duration videos are rejected.

    For any video file with duration_seconds > 300, the video pipeline SHALL
    reject the file with an appropriate error message.

    **Validates: Requirements 4.6**
    """
    fmt, size_bytes, duration_seconds = metadata

    # Create a temporary file with valid extension
    with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"\x00" * 100)

    try:
        state = _create_video_pipeline_state(tmp_path)

        # Mock format and size to pass, but duration exceeds limit
        with patch(
            "culture_compliance.nodes.step2_video_analysis._detect_video_format_by_extension",
            return_value=fmt,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._get_file_size",
            return_value=size_bytes,
        ), patch(
            "culture_compliance.nodes.step2_video_analysis._get_video_duration",
            return_value=duration_seconds,
        ), patch(
            "os.path.exists",
            return_value=True,
        ):
            result_state = video_processing(state)

        # Over-duration videos should produce a validation error
        validation_errors = [
            e for e in result_state.errors if e.get("error_type") == "validation"
        ]
        assert len(validation_errors) > 0, (
            f"Over-duration video ({duration_seconds}s) was not rejected"
        )

        # Error message should mention duration
        error_msg = validation_errors[0]["message"].lower()
        assert "duration" in error_msg or "minute" in error_msg or "second" in error_msg, (
            f"Error message does not mention duration: {validation_errors[0]['message']}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
