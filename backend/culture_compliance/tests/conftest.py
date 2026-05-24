"""Shared fixtures and Hypothesis profiles for content compliance tests.

Provides:
- Hypothesis profile configuration (default: 100 examples, 5000ms deadline)
- Mock Qdrant client fixture for guideline retrieval tests
- Mock Bedrock client fixture for LLM evaluation tests
- Sample data fixtures for common test scenarios
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import settings, HealthCheck

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    ProcessingMetadata,
)


# --- Hypothesis Profile Configuration ---

settings.register_profile(
    "default",
    max_examples=100,
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "ci",
    max_examples=200,
    deadline=10000,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "dev",
    max_examples=20,
    deadline=10000,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.load_profile("default")


# --- Mock Qdrant Client Fixture ---


@pytest.fixture
def mock_qdrant_client():
    """Provide a mock Qdrant client that returns sample guideline results.

    The mock simulates successful vector search returning 5 guideline chunks
    with relevance scores. Use this fixture to test guideline retrieval
    without requiring a live Qdrant instance.
    """
    mock_client = MagicMock()

    # Simulate search results with scored points
    mock_point = MagicMock()
    mock_point.payload = {
        "source_authority": "MCMC",
        "topic_category": "Religious Sensitivity",
        "guideline_text": "Content must not offend religious sensitivities of any community.",
    }
    mock_point.score = 0.92

    mock_client.search.return_value = [mock_point] * 5
    mock_client.get_collection.return_value = MagicMock(
        points_count=100,
        vectors_count=100,
    )

    return mock_client


# --- Mock Bedrock Client Fixture ---


@pytest.fixture
def mock_bedrock_client():
    """Provide a mock Bedrock client that returns a sample LLM response.

    The mock simulates a successful Bedrock Converse API call returning
    a structured compliance evaluation JSON. Use this fixture to test
    compliance evaluation without requiring AWS credentials.
    """
    mock_client = MagicMock()

    # Simulate a successful converse response
    mock_response = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"risk_level": "Low", "score": 85, '
                        '"high_risk_indicators": [], '
                        '"explanation": "Content appears compliant.", '
                        '"suggestion": "No changes needed."}'
                    }
                ]
            }
        },
        "usage": {"inputTokens": 500, "outputTokens": 200},
        "metrics": {"latencyMs": 1200},
    }
    mock_client.converse.return_value = mock_response

    return mock_client


# --- Sample Data Fixtures ---


@pytest.fixture
def sample_text_submission():
    """Provide a sample text ContentSubmission for testing."""
    return ContentSubmission(
        content="Buy our halal-certified products today!",
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
    )


@pytest.fixture
def sample_image_submission():
    """Provide a sample image ContentSubmission with minimal base64 content."""
    # Minimal valid base64 content (not a real image, but passes content validation)
    import base64

    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    content = base64.b64encode(fake_image_bytes).decode("ascii")
    return ContentSubmission(
        content=content,
        content_type=ContentType.IMAGE,
        market=Market.MALAYSIA,
    )


@pytest.fixture
def sample_video_submission():
    """Provide a sample video ContentSubmission with S3 URI."""
    return ContentSubmission(
        content="s3://compliance-bucket/videos/test-ad.mp4",
        content_type=ContentType.VIDEO,
        market=Market.SINGAPORE,
        frame_interval_seconds=2.0,
    )


@pytest.fixture
def sample_processing_metadata():
    """Provide sample ProcessingMetadata for result construction."""
    return ProcessingMetadata(
        pipeline_duration_ms=2500,
        models_used=["amazon.nova-pro-v1:0", "cohere.embed-english-v3"],
        market="malaysia",
    )


# --- Mock Service Fixtures ---


@pytest.fixture
def mock_vision_service():
    """Provide a mock vision service that returns a sample description."""
    with patch(
        "culture_compliance.services.vision.analyze_image"
    ) as mock_fn:
        mock_fn.return_value = "Image shows a family dining scene with traditional food."
        yield mock_fn


@pytest.fixture
def mock_ocr_service():
    """Provide a mock OCR service that returns sample extracted text."""
    with patch(
        "culture_compliance.services.ocr.extract_text_from_image"
    ) as mock_fn:
        mock_fn.return_value = "SPECIAL OFFER - 50% OFF"
        yield mock_fn


@pytest.fixture
def mock_transcriber_service():
    """Provide a mock transcriber service that returns sample segments."""
    with patch(
        "culture_compliance.services.transcriber.transcribe_audio"
    ) as mock_fn:
        mock_fn.return_value = [
            {"start_time": 0.0, "end_time": 3.5, "text": "Welcome to our store."},
            {"start_time": 3.5, "end_time": 7.0, "text": "Check out our new products."},
        ]
        yield mock_fn
