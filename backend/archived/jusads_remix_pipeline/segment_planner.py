"""Segment Planner for the JusAds Video Remix Pipeline.

Splits non-compliant video segments into generation-compatible chunks
(5-8 seconds each) for downstream storyboard generation and video interpolation.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

from __future__ import annotations

import math


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIN_CHUNK_DURATION = 5.0  # seconds
MAX_CHUNK_DURATION = 8.0  # seconds
SHORT_FORM_THRESHOLD = 5.0  # segments below this are flagged as short-form


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def plan_segments(
    violations: list[dict], video_duration: float
) -> list[dict] | dict:
    """Plan generation segments for non-compliant video sections.

    Takes a list of video violations (each with start/end timestamps) and the
    total video duration. Produces a segment plan that maps each chunk to its
    timing, source violation, and sequence number.

    Args:
        violations: List of violation dicts, each containing at minimum:
            - index (int): Non-negative violation identifier
            - start (float): Start time in seconds
            - end (float): End time in seconds
        video_duration: Total video duration in seconds.

    Returns:
        On success, a list of chunk dicts with:
            - start_time (float): Start of this chunk in seconds
            - end_time (float): End of this chunk in seconds
            - source_violation_index (int): Which violation this chunk belongs to
            - chunk_sequence_number (int): Sequence within the violation (0-based)
            - is_short_form (bool): True if original segment < 5 seconds

        On validation error, a dict with:
            - error (str): Description of the validation failure
    """
    # Validate all violations first
    for violation in violations:
        validation_error = _validate_violation(violation)
        if validation_error:
            return {"error": validation_error}

    # Build the segment plan from all violations
    segment_plan: list[dict] = []

    for violation in violations:
        start = float(violation["start"])
        end = float(violation["end"])
        violation_index = int(violation["index"])
        duration = end - start

        chunks = _split_segment(start, end, duration)

        for seq_num, (chunk_start, chunk_end) in enumerate(chunks):
            segment_plan.append(
                {
                    "start_time": chunk_start,
                    "end_time": chunk_end,
                    "source_violation_index": violation_index,
                    "chunk_sequence_number": seq_num,
                    "is_short_form": duration < SHORT_FORM_THRESHOLD,
                }
            )

    return segment_plan


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIVATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _validate_violation(violation: dict) -> str | None:
    """Validate a single violation dict. Returns error message or None."""
    start = violation.get("start")
    end = violation.get("end")

    if start is None or end is None:
        return "Violation missing required 'start' or 'end' field"

    try:
        start_val = float(start)
        end_val = float(end)
    except (TypeError, ValueError):
        return f"Invalid timestamp values: start={start}, end={end}"

    if end_val <= start_val:
        return (
            f"Invalid time range for violation {violation.get('index', '?')}: "
            f"end ({end_val}) must be greater than start ({start_val})"
        )

    return None


def _split_segment(
    start: float, end: float, duration: float
) -> list[tuple[float, float]]:
    """Split a segment into chunks respecting the 5-8 second constraint.

    Strategy:
    - Segments <= 8s: keep as a single chunk (whether short-form or normal)
    - Segments > 8s: split into evenly-sized chunks where each is 5-8s
      The number of chunks is chosen so that each chunk duration falls
      within [5, 8] seconds.

    Returns:
        List of (chunk_start, chunk_end) tuples.
    """
    if duration <= MAX_CHUNK_DURATION:
        # Segment fits within the max — keep as single chunk (Req 4.2, 4.5)
        return [(start, end)]

    # Segment exceeds 8 seconds — need to split (Req 4.1)
    # Calculate the number of chunks needed so each is between 5-8s.
    # We need: num_chunks such that 5 <= duration/num_chunks <= 8
    # So: duration/8 <= num_chunks <= duration/5
    num_chunks = math.ceil(duration / MAX_CHUNK_DURATION)

    # Verify all chunks will be at least MIN_CHUNK_DURATION
    # If not, reduce chunk count (shouldn't happen with ceil, but safety check)
    while num_chunks > 1 and (duration / num_chunks) < MIN_CHUNK_DURATION:
        num_chunks -= 1

    # Split evenly across the number of chunks
    chunk_duration = duration / num_chunks
    chunks: list[tuple[float, float]] = []

    for i in range(num_chunks):
        chunk_start = start + i * chunk_duration
        # Use exact end for the last chunk to avoid floating-point drift
        chunk_end = end if i == num_chunks - 1 else start + (i + 1) * chunk_duration
        chunks.append((chunk_start, chunk_end))

    return chunks
