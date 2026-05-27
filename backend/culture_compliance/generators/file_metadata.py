"""Hypothesis strategies for file metadata validation testing.

Provides strategies for generating valid and invalid image/video file metadata
to test the file validation logic in the image and video pipelines.

Image constraints (from Requirements 3.5, 3.6, 3.7):
- Format: JPEG, PNG, WebP
- Size: <= 5 MB (5,242,880 bytes)
- Resolution: >= 50x50 pixels

Video constraints (from Requirements 4.6, 4.7):
- Format: MP4, MOV, WebM
- Size: <= 100 MB (104,857,600 bytes)
- Duration: <= 300 seconds (5 minutes)
"""

from hypothesis import strategies as st


# --- Constants ---

VALID_IMAGE_FORMATS = ["JPEG", "PNG", "WebP"]
INVALID_IMAGE_FORMATS = ["GIF", "BMP", "TIFF", "SVG", "HEIC", "RAW", "ICO"]

MAX_IMAGE_SIZE_BYTES = 5_242_880  # 5 MB
MIN_IMAGE_DIMENSION = 50

VALID_VIDEO_FORMATS = ["MP4", "MOV", "WebM"]
INVALID_VIDEO_FORMATS = ["AVI", "FLV", "WMV", "MKV", "MPEG", "3GP"]

MAX_VIDEO_SIZE_BYTES = 104_857_600  # 100 MB
MAX_VIDEO_DURATION_SECONDS = 300  # 5 minutes


# --- Image metadata strategies ---


def valid_image_metadata_strategy():
    """Strategy for generating image metadata that passes all validation rules.

    Generates combinations where:
    - format is in {JPEG, PNG, WebP}
    - size_bytes <= 5,242,880
    - width >= 50
    - height >= 50

    Returns:
        A Hypothesis strategy producing dicts with keys:
        format, size_bytes, width, height.
    """
    return st.fixed_dictionaries({
        "format": st.sampled_from(VALID_IMAGE_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_IMAGE_SIZE_BYTES),
        "width": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "height": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
    })


def invalid_image_metadata_strategy():
    """Strategy for generating image metadata that fails at least one validation rule.

    Generates combinations where at least one of:
    - format is NOT in {JPEG, PNG, WebP}
    - size_bytes > 5,242,880
    - width < 50
    - height < 50

    Returns:
        A Hypothesis strategy producing dicts with keys:
        format, size_bytes, width, height, and a 'violation' key
        indicating which rule is violated.
    """
    # Strategy: invalid format
    invalid_format = st.fixed_dictionaries({
        "format": st.sampled_from(INVALID_IMAGE_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_IMAGE_SIZE_BYTES),
        "width": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "height": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "violation": st.just("format"),
    })

    # Strategy: oversized file
    oversized = st.fixed_dictionaries({
        "format": st.sampled_from(VALID_IMAGE_FORMATS),
        "size_bytes": st.integers(
            min_value=MAX_IMAGE_SIZE_BYTES + 1, max_value=MAX_IMAGE_SIZE_BYTES * 10
        ),
        "width": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "height": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "violation": st.just("size"),
    })

    # Strategy: width too small
    small_width = st.fixed_dictionaries({
        "format": st.sampled_from(VALID_IMAGE_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_IMAGE_SIZE_BYTES),
        "width": st.integers(min_value=1, max_value=MIN_IMAGE_DIMENSION - 1),
        "height": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "violation": st.just("width"),
    })

    # Strategy: height too small
    small_height = st.fixed_dictionaries({
        "format": st.sampled_from(VALID_IMAGE_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_IMAGE_SIZE_BYTES),
        "width": st.integers(min_value=MIN_IMAGE_DIMENSION, max_value=10000),
        "height": st.integers(min_value=1, max_value=MIN_IMAGE_DIMENSION - 1),
        "violation": st.just("height"),
    })

    return st.one_of(invalid_format, oversized, small_width, small_height)


# --- Video metadata strategies ---


def valid_video_metadata_strategy():
    """Strategy for generating video metadata that passes all validation rules.

    Generates combinations where:
    - format is in {MP4, MOV, WebM}
    - size_bytes <= 104,857,600
    - duration_seconds <= 300

    Returns:
        A Hypothesis strategy producing dicts with keys:
        format, size_bytes, duration_seconds.
    """
    return st.fixed_dictionaries({
        "format": st.sampled_from(VALID_VIDEO_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES),
        "duration_seconds": st.floats(
            min_value=0.1,
            max_value=MAX_VIDEO_DURATION_SECONDS,
            allow_nan=False,
            allow_infinity=False,
        ),
    })


def invalid_video_metadata_strategy():
    """Strategy for generating video metadata that fails at least one validation rule.

    Generates combinations where at least one of:
    - format is NOT in {MP4, MOV, WebM}
    - size_bytes > 104,857,600
    - duration_seconds > 300

    Returns:
        A Hypothesis strategy producing dicts with keys:
        format, size_bytes, duration_seconds, and a 'violation' key
        indicating which rule is violated.
    """
    # Strategy: invalid format
    invalid_format = st.fixed_dictionaries({
        "format": st.sampled_from(INVALID_VIDEO_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES),
        "duration_seconds": st.floats(
            min_value=0.1,
            max_value=MAX_VIDEO_DURATION_SECONDS,
            allow_nan=False,
            allow_infinity=False,
        ),
        "violation": st.just("format"),
    })

    # Strategy: oversized file
    oversized = st.fixed_dictionaries({
        "format": st.sampled_from(VALID_VIDEO_FORMATS),
        "size_bytes": st.integers(
            min_value=MAX_VIDEO_SIZE_BYTES + 1, max_value=MAX_VIDEO_SIZE_BYTES * 5
        ),
        "duration_seconds": st.floats(
            min_value=0.1,
            max_value=MAX_VIDEO_DURATION_SECONDS,
            allow_nan=False,
            allow_infinity=False,
        ),
        "violation": st.just("size"),
    })

    # Strategy: duration too long
    too_long = st.fixed_dictionaries({
        "format": st.sampled_from(VALID_VIDEO_FORMATS),
        "size_bytes": st.integers(min_value=1, max_value=MAX_VIDEO_SIZE_BYTES),
        "duration_seconds": st.floats(
            min_value=MAX_VIDEO_DURATION_SECONDS + 0.1,
            max_value=MAX_VIDEO_DURATION_SECONDS * 10,
            allow_nan=False,
            allow_infinity=False,
        ),
        "violation": st.just("duration"),
    })

    return st.one_of(invalid_format, oversized, too_long)
