"""Compliance checker wrapping the existing culture_compliance pipeline.

Invokes the culture_compliance orchestrator to check a video against
market-specific cultural and regulatory compliance rules, then parses
the results into structured Violation objects with precise timestamps.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from typing import Optional

from jusads_video_compliance.models import ComplianceCheckResult, Violation

logger = logging.getLogger(__name__)

# Pipeline timeout in seconds (Requirement 1.7)
PIPELINE_TIMEOUT_SECONDS = 120

# Maximum number of violations to return (Requirement 1.1)
MAX_VIOLATIONS = 10

# Audio-related keywords for violation_type classification
AUDIO_KEYWORDS = [
    "audio",
    "spoken",
    "dialogue",
    "voiceover",
    "voice",
    "speech",
    "narration",
    "soundtrack",
    "music",
    "sound",
    "verbal",
    "claim",
    "says",
    "said",
    "mentions",
    "states",
    "transcript",
]


def _get_video_duration(video_path: str) -> Optional[float]:
    """Get the duration of a video file using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds, or None if it cannot be determined.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning("Failed to get video duration: %s", e)
    return None


def _parse_timestamp(timestamp_str: str) -> float:
    """Convert a timestamp string (MM:SS or HH:MM:SS) to float seconds.

    Args:
        timestamp_str: Timestamp in "MM:SS" or "HH:MM:SS" format.

    Returns:
        Time in seconds as a float.

    Raises:
        ValueError: If the timestamp format is invalid.
    """
    parts = timestamp_str.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return minutes * 60.0 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return hours * 3600.0 + minutes * 60.0 + seconds
    else:
        raise ValueError(f"Invalid timestamp format: '{timestamp_str}'")


def _determine_violation_type(indicator_text: str) -> str:
    """Determine whether a violation is visual or audio based on its text.

    Checks for audio-related keywords in the indicator text. If any are
    found, classifies as "audio"; otherwise defaults to "visual".

    Args:
        indicator_text: The high_risk_indicator string from the pipeline.

    Returns:
        "audio" or "visual"
    """
    text_lower = indicator_text.lower()
    for keyword in AUDIO_KEYWORDS:
        if keyword in text_lower:
            return "audio"
    return "visual"


def _determine_severity(indicator_text: str, score: int) -> str:
    """Determine severity level from indicator text and overall score.

    Heuristic: if the score is very low (< 40), indicators are likely Severe.
    If moderate (40-74), they're Moderate. Otherwise Minor.
    Individual indicators mentioning severity keywords override this.

    Args:
        indicator_text: The high_risk_indicator string.
        score: The overall compliance score.

    Returns:
        "Severe", "Moderate", or "Minor"
    """
    text_lower = indicator_text.lower()

    # Check for explicit severity keywords in the text
    if any(word in text_lower for word in ["severe", "critical", "explicit", "nudity", "hate"]):
        return "Severe"
    if any(word in text_lower for word in ["moderate", "inappropriate", "offensive"]):
        return "Moderate"
    if any(word in text_lower for word in ["minor", "slight", "subtle"]):
        return "Minor"

    # Fall back to score-based heuristic
    if score < 40:
        return "Severe"
    elif score < 75:
        return "Moderate"
    else:
        return "Minor"


def _determine_guideline_source(indicator_text: str) -> str:
    """Determine guideline source from indicator text.

    Checks for regulatory-related keywords. If found, classifies as
    "regulatory"; otherwise defaults to "cultural".

    Args:
        indicator_text: The high_risk_indicator string.

    Returns:
        "regulatory" or "cultural"
    """
    text_lower = indicator_text.lower()
    regulatory_keywords = [
        "regulatory", "regulation", "law", "legal", "code",
        "mcmc", "imda", "asas", "act", "statute",
    ]
    for keyword in regulatory_keywords:
        if keyword in text_lower:
            return "regulatory"
    return "cultural"


def _parse_indicator_to_violation(
    indicator: str,
    score: int,
    video_duration: Optional[float],
) -> Optional[Violation]:
    """Parse a single high_risk_indicator string into a Violation object.

    Expected format: "[MM:SS-MM:SS] Description (Visual/Audio)"
    or "[MM:SS] Description" (single timestamp, uses +2s as end).

    Args:
        indicator: The raw indicator string from the pipeline.
        score: The overall compliance score (used for severity heuristic).
        video_duration: Duration of the video in seconds, or None.

    Returns:
        A Violation object, or None if parsing fails.
    """
    if not indicator or not isinstance(indicator, str):
        return None

    # Try to extract timestamp range: [MM:SS-MM:SS] or [HH:MM:SS-HH:MM:SS]
    range_pattern = r"\[(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(\d{1,2}:\d{2}(?::\d{2})?)\]"
    single_pattern = r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]"

    timestamp_start = None
    timestamp_end = None
    description = indicator

    range_match = re.search(range_pattern, indicator)
    if range_match:
        try:
            timestamp_start = _parse_timestamp(range_match.group(1))
            timestamp_end = _parse_timestamp(range_match.group(2))
            # Remove the timestamp portion from description
            description = indicator[range_match.end():].strip()
        except ValueError:
            timestamp_start = None
            timestamp_end = None
    else:
        single_match = re.search(single_pattern, indicator)
        if single_match:
            try:
                timestamp_start = _parse_timestamp(single_match.group(1))
                # Default end = start + 2 seconds
                timestamp_end = timestamp_start + 2.0
                description = indicator[single_match.end():].strip()
            except ValueError:
                timestamp_start = None

    # If no timestamps could be parsed, use defaults
    if timestamp_start is None:
        timestamp_start = 0.0
        timestamp_end = 2.0
        description = indicator

    if timestamp_end is None:
        timestamp_end = timestamp_start + 2.0

    # Ensure timestamp_end > timestamp_start
    if timestamp_end <= timestamp_start:
        timestamp_end = timestamp_start + 1.0

    # Validate timestamps within video duration (Requirement 1.6)
    if video_duration is not None:
        timestamp_start = max(0.0, min(timestamp_start, video_duration - 0.1))
        timestamp_end = min(timestamp_end, video_duration)
        # Ensure end > start after clamping
        if timestamp_end <= timestamp_start:
            timestamp_end = min(timestamp_start + 1.0, video_duration)

    # Truncate description to 200 chars
    if len(description) > 200:
        description = description[:197] + "..."

    # Determine violation attributes
    violation_type = _determine_violation_type(indicator)
    severity = _determine_severity(indicator, score)
    guideline_source = _determine_guideline_source(indicator)

    # Determine category from the indicator text
    category = _extract_category(indicator)

    try:
        return Violation(
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            category=category,
            severity=severity,
            description=description,
            violation_type=violation_type,
            guideline_source=guideline_source,
        )
    except ValueError as e:
        logger.warning("Failed to create Violation from indicator '%s': %s", indicator, e)
        return None


def _extract_category(indicator_text: str) -> str:
    """Extract the violation category from indicator text.

    Maps keywords in the indicator to known VIOLATION_CATEGORIES.

    Args:
        indicator_text: The raw indicator string.

    Returns:
        A category string matching one of the known categories.
    """
    text_lower = indicator_text.lower()

    category_keywords = {
        "Religious Sensitivity": ["religious", "religion", "halal", "haram", "mosque", "temple", "church", "prayer", "faith", "god", "allah"],
        "Ethnic/Racial": ["ethnic", "racial", "race", "skin color", "skin colour", "stereotype", "discrimination"],
        "Sexual/Explicit": ["sexual", "explicit", "nudity", "nude", "revealing", "cleavage", "exposed", "sleeveless", "modesty", "immodest", "tank top", "bikini", "underwear", "lingerie", "armpit"],
        "Political/State": ["political", "government", "state", "flag", "national", "sedition", "royalty", "sultan"],
        "LGBTQ": ["lgbtq", "lgbt", "gay", "lesbian", "transgender", "homosexual", "same-sex"],
        "Profanity": ["profanity", "profane", "vulgar", "swear", "curse", "obscene", "offensive language"],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category

    # Default category if no match
    return "Sexual/Explicit"


def _compute_risk_level(score: int) -> str:
    """Compute risk level from compliance score.

    Score >= 75 → "Low"
    40 <= Score < 75 → "Medium"
    Score < 40 → "High"

    Args:
        score: Compliance score in range [0, 100].

    Returns:
        "High", "Medium", or "Low"
    """
    if score >= 75:
        return "Low"
    elif score >= 40:
        return "Medium"
    else:
        return "High"


def _run_pipeline_sync(video_path: str, market: str, target_ethnicity: str, target_age_group: str) -> dict:
    """Run the culture_compliance pipeline synchronously.

    Tries the LangGraph-based orchestrator first. If that fails (e.g., due to
    import issues or missing dependencies), falls back to the VideoComplianceChecker.

    Args:
        video_path: Path to the video file.
        market: Target market.
        target_ethnicity: Target ethnicity.
        target_age_group: Target age group.

    Returns:
        Pipeline result dictionary.
    """
    # Try the LangGraph orchestrator first
    try:
        from culture_compliance.orchestrator import run_pipeline
        from culture_compliance.models.schemas import ContentSubmission, ContentType, Market

        market_enum = Market(market.lower())
        submission = ContentSubmission(
            content=video_path,
            content_type=ContentType.VIDEO,
            market=market_enum,
            target_ethnicity=target_ethnicity,
            target_age_group=target_age_group,
        )
        result = run_pipeline(submission)

        # run_pipeline returns either a ComplianceResult dict or a dict with error info
        if isinstance(result, dict):
            return result
        # If it's a Pydantic model, convert to dict
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    except ImportError as e:
        logger.warning("LangGraph orchestrator not available: %s. Falling back to VideoComplianceChecker.", e)
    except Exception as e:
        logger.warning("LangGraph orchestrator failed: %s. Falling back to VideoComplianceChecker.", e)

    # Fallback: use the VideoComplianceChecker directly
    try:
        from jusads_video_compliance.video_checker import VideoComplianceChecker

        checker = VideoComplianceChecker()
        return checker.check_compliance(
            video_path=video_path,
            market=market,
            ethnicity=target_ethnicity,
            age_group=target_age_group,
        )
    except Exception as e:
        logger.error("VideoComplianceChecker also failed: %s", e)
        raise


async def check_compliance(
    video_path: str,
    market: str,
    target_ethnicity: str,
    target_age_group: str,
) -> ComplianceCheckResult:
    """Run the existing culture_compliance pipeline on a video.

    Invokes the culture_compliance pipeline with a timeout, parses the
    results into structured Violation objects, and returns a
    ComplianceCheckResult.

    Args:
        video_path: Path to the video file (MP4/MOV/WebM).
        market: Target market ("malaysia" or "singapore").
        target_ethnicity: Target ethnicity ("malay", "chinese", "indian", or "all").
        target_age_group: Target age group ("all_ages", "adults_only", or "children").

    Returns:
        ComplianceCheckResult with risk level, score, and violations.

    Raises:
        TimeoutError: If the pipeline does not respond within 120 seconds.
        RuntimeError: If the pipeline returns an error.
    """
    # Get video duration for timestamp validation
    video_duration = _get_video_duration(video_path)

    # Run the pipeline with timeout (Requirement 1.7)
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _run_pipeline_sync,
                video_path,
                market,
                target_ethnicity,
                target_age_group,
            ),
            timeout=PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Culture compliance pipeline did not respond within "
            f"{PIPELINE_TIMEOUT_SECONDS} seconds"
        )
    except Exception as e:
        raise RuntimeError(f"Culture compliance pipeline error: {e}") from e

    # Extract score and compute risk level
    raw_score = result.get("score", result.get("SCORE", 0))
    if isinstance(raw_score, str):
        try:
            raw_score = int(raw_score)
        except (ValueError, TypeError):
            raw_score = 0

    # Clamp score to [0, 100]
    score = max(0, min(100, raw_score))
    risk_level = _compute_risk_level(score)

    # Parse high_risk_indicators into Violation objects
    raw_indicators = result.get(
        "high_risk_indicators",
        result.get("high_risk_indicator", []),
    )

    violations: list[Violation] = []
    if isinstance(raw_indicators, list):
        for indicator in raw_indicators[:MAX_VIOLATIONS]:
            if isinstance(indicator, str):
                violation = _parse_indicator_to_violation(
                    indicator, score, video_duration
                )
                if violation is not None:
                    violations.append(violation)

    # Enforce max 10 violations (Requirement 1.1)
    violations = violations[:MAX_VIOLATIONS]

    # Extract explanation and suggestion
    explanation = result.get("explanation", "")
    suggestion = result.get("suggestion", "")

    return ComplianceCheckResult(
        risk_level=risk_level,
        score=score,
        violations=violations,
        explanation=explanation,
        suggestion=suggestion,
        raw_result=result,
    )
