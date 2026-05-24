"""Hypothesis strategies for generating ContentSubmission objects.

Provides strategies for creating valid and targeted ContentSubmission instances
for property-based testing of the content compliance pipeline.

Validates: Requirements 1.1, 11.1, 6.5
"""

import base64
import string

from hypothesis import strategies as st

from culture_compliance.models.schemas import ContentType, Market


# --- Base strategies ---

# Non-empty text content (at least one non-whitespace character)
_non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=500,
).filter(lambda s: s.strip())

# Base64-encoded image content (simulated small image data)
_base64_image_content = st.binary(
    min_size=100, max_size=2000
).map(lambda b: base64.b64encode(b).decode("ascii"))

# S3 URI for video content
_s3_video_uri = st.from_regex(
    r"s3://[a-z][a-z0-9\-]{2,62}/[a-zA-Z0-9/\-_.]{1,100}\.(mp4|mov|webm)",
    fullmatch=True,
)

# Valid market values
_valid_market = st.sampled_from(list(Market))

# Valid frame interval (0.5 to 5.0 seconds)
_valid_frame_interval = st.floats(min_value=0.5, max_value=5.0)

# Valid ethnicity values for cultural guideline filtering
_valid_ethnicity = st.sampled_from(["malay", "chinese", "indian", "all"])

# Valid age group values for cultural guideline filtering
_valid_age_group = st.sampled_from(["all_ages", "adults_only", "children"])


# --- ContentSubmission strategies ---


def ethnicity_strategy():
    """Strategy for valid target_ethnicity values.

    Returns:
        A Hypothesis strategy producing one of: "malay", "chinese", "indian", "all".
    """
    return _valid_ethnicity


def age_group_strategy():
    """Strategy for valid target_age_group values.

    Returns:
        A Hypothesis strategy producing one of: "all_ages", "adults_only", "children".
    """
    return _valid_age_group


def text_submission_strategy(
    content=None,
    market=None,
    target_ethnicity=None,
    target_age_group=None,
):
    """Strategy for generating text ContentSubmission objects.

    Args:
        content: Optional override for the content field.
        market: Optional override for the market field.
        target_ethnicity: Optional override for target_ethnicity field.
        target_age_group: Optional override for target_age_group field.

    Returns:
        A Hypothesis strategy producing dict kwargs for ContentSubmission.
    """
    return st.fixed_dictionaries({
        "content": content or _non_empty_text,
        "content_type": st.just("text"),
        "market": market or _valid_market,
        "frame_interval_seconds": st.just(1.0),
        "target_ethnicity": target_ethnicity or _valid_ethnicity,
        "target_age_group": target_age_group or _valid_age_group,
    })


def image_submission_strategy(
    content=None,
    market=None,
    target_ethnicity=None,
    target_age_group=None,
):
    """Strategy for generating image ContentSubmission objects.

    Args:
        content: Optional override for the content field.
        market: Optional override for the market field.
        target_ethnicity: Optional override for target_ethnicity field.
        target_age_group: Optional override for target_age_group field.

    Returns:
        A Hypothesis strategy producing dict kwargs for ContentSubmission.
    """
    return st.fixed_dictionaries({
        "content": content or _base64_image_content,
        "content_type": st.just("image"),
        "market": market or _valid_market,
        "frame_interval_seconds": st.just(1.0),
        "target_ethnicity": target_ethnicity or _valid_ethnicity,
        "target_age_group": target_age_group or _valid_age_group,
    })


def video_submission_strategy(
    content=None,
    market=None,
    frame_interval=None,
    target_ethnicity=None,
    target_age_group=None,
):
    """Strategy for generating video ContentSubmission objects.

    Args:
        content: Optional override for the content field.
        market: Optional override for the market field.
        frame_interval: Optional override for frame_interval_seconds.
        target_ethnicity: Optional override for target_ethnicity field.
        target_age_group: Optional override for target_age_group field.

    Returns:
        A Hypothesis strategy producing dict kwargs for ContentSubmission.
    """
    return st.fixed_dictionaries({
        "content": content or _s3_video_uri,
        "content_type": st.just("video"),
        "market": market or _valid_market,
        "frame_interval_seconds": frame_interval or _valid_frame_interval,
        "target_ethnicity": target_ethnicity or _valid_ethnicity,
        "target_age_group": target_age_group or _valid_age_group,
    })


def content_submission_strategy(
    content_type=None,
    market=None,
    target_ethnicity=None,
    target_age_group=None,
):
    """Strategy for generating any valid ContentSubmission.

    Randomly selects between text, image, and video submissions.

    Args:
        content_type: Optional fixed content type. If None, randomly chosen.
        market: Optional override for the market field.
        target_ethnicity: Optional override for target_ethnicity field.
        target_age_group: Optional override for target_age_group field.

    Returns:
        A Hypothesis strategy producing dict kwargs for ContentSubmission.
    """
    if content_type is not None:
        if content_type == "text":
            return text_submission_strategy(
                market=market,
                target_ethnicity=target_ethnicity,
                target_age_group=target_age_group,
            )
        elif content_type == "image":
            return image_submission_strategy(
                market=market,
                target_ethnicity=target_ethnicity,
                target_age_group=target_age_group,
            )
        elif content_type == "video":
            return video_submission_strategy(
                market=market,
                target_ethnicity=target_ethnicity,
                target_age_group=target_age_group,
            )

    return st.one_of(
        text_submission_strategy(
            market=market,
            target_ethnicity=target_ethnicity,
            target_age_group=target_age_group,
        ),
        image_submission_strategy(
            market=market,
            target_ethnicity=target_ethnicity,
            target_age_group=target_age_group,
        ),
        video_submission_strategy(
            market=market,
            target_ethnicity=target_ethnicity,
            target_age_group=target_age_group,
        ),
    )
