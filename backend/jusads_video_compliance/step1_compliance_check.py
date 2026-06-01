"""
Step 1: Compliance Check
==========================
Checks a video against cultural/regulatory guidelines using Gemini + Qdrant RAG.
Returns risk level, score, and high-risk indicators with timestamps.
"""

from jusads_video_compliance.video_checker import VideoComplianceChecker


def check_compliance(video_path: str, market: str, ethnicity: str, age_group: str) -> dict:
    """
    Run compliance check on a video.

    Args:
        video_path: Path to the video file.
        market: Target market (e.g. 'malaysia', 'singapore').
        ethnicity: Target ethnicity (e.g. 'malay', 'chinese', 'indian').
        age_group: Target age group.

    Returns:
        Dict with risk_level, score, high_risk_indicators, explanation, suggestion.
    """
    checker = VideoComplianceChecker()
    return checker.check_compliance(
        video_path=video_path,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
    )
