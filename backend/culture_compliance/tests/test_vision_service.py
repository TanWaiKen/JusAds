"""Unit tests for the vision service.

Tests the analyze_image function with mocked Bedrock client to verify:
- Successful image analysis returns a description string
- Empty image bytes returns empty string
- Model unavailability is handled gracefully (returns empty string)
- Image format detection works for JPEG, PNG, and WebP

Requirements: 3.1, 3.8
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from culture_compliance.services.vision import (
    analyze_image,
    _detect_media_type,
    VISION_MODEL_ID,
)


# --- Sample image magic bytes for format detection ---

JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP_MAGIC = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100
UNKNOWN_MAGIC = b"\x00\x01\x02\x03" + b"\x00" * 100


class TestDetectMediaType:
    """Tests for image format detection from magic bytes."""

    def test_detects_jpeg(self):
        assert _detect_media_type(JPEG_MAGIC) == "jpeg"

    def test_detects_png(self):
        assert _detect_media_type(PNG_MAGIC) == "png"

    def test_detects_webp(self):
        assert _detect_media_type(WEBP_MAGIC) == "webp"

    def test_defaults_to_jpeg_for_unknown(self):
        assert _detect_media_type(UNKNOWN_MAGIC) == "jpeg"


class TestAnalyzeImage:
    """Tests for the analyze_image function."""

    def test_empty_bytes_returns_empty_string(self):
        """Empty image bytes should return empty string without calling Bedrock."""
        result = analyze_image(b"")
        assert result == ""

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_successful_analysis_returns_description(self, mock_get_client):
        """Successful Bedrock call should return the model's text response."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        expected_description = (
            "The image shows a billboard advertisement featuring a family "
            "in a park setting. There is text overlay reading 'Family First'. "
            "No sensitive content detected."
        )

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": expected_description}]
                }
            }
        }

        result = analyze_image(JPEG_MAGIC)

        assert result == expected_description
        mock_client.converse.assert_called_once()

        # Verify the call used the correct model ID
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["modelId"] == VISION_MODEL_ID

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_sends_image_bytes_directly(self, mock_get_client):
        """Image bytes should be sent directly in the message content."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "A test image."}]
                }
            }
        }

        analyze_image(PNG_MAGIC)

        call_kwargs = mock_client.converse.call_args[1]
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

        content = messages[0]["content"]
        # Should have image block and text block
        assert len(content) == 2

        image_block = content[0]
        assert "image" in image_block
        assert image_block["image"]["format"] == "png"
        assert image_block["image"]["source"]["bytes"] == PNG_MAGIC

        text_block = content[1]
        assert "text" in text_block

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_client_error_returns_empty_string(self, mock_get_client):
        """ClientError (model unavailable) should return empty string gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ModelNotReadyException",
                    "Message": "Model is not available",
                }
            },
            operation_name="Converse",
        )

        result = analyze_image(JPEG_MAGIC)

        assert result == ""

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_throttling_error_returns_empty_string(self, mock_get_client):
        """ThrottlingException should return empty string gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Rate exceeded",
                }
            },
            operation_name="Converse",
        )

        result = analyze_image(JPEG_MAGIC)

        assert result == ""

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_unexpected_error_returns_empty_string(self, mock_get_client):
        """Any unexpected exception should return empty string gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.side_effect = RuntimeError("Unexpected network error")

        result = analyze_image(JPEG_MAGIC)

        assert result == ""

    @patch("culture_compliance.services.vision._get_bedrock_client")
    def test_webp_format_detected_correctly(self, mock_get_client):
        """WebP images should be sent with format='webp'."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "A webp image."}]
                }
            }
        }

        analyze_image(WEBP_MAGIC)

        call_kwargs = mock_client.converse.call_args[1]
        image_block = call_kwargs["messages"][0]["content"][0]
        assert image_block["image"]["format"] == "webp"
