"""Unit tests for the OCR service.

Tests the extract_text_from_image function with mocked Bedrock responses
to verify correct behavior for text extraction, error handling, and
media type detection.
"""

from unittest.mock import MagicMock, patch

import pytest

from culture_compliance.services.ocr import (
    _detect_media_type,
    extract_text_from_image,
)


# --- Media type detection tests ---


class TestDetectMediaType:
    """Tests for _detect_media_type helper."""

    def test_detects_jpeg(self):
        """JPEG files start with FF D8."""
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert _detect_media_type(jpeg_bytes) == "jpeg"

    def test_detects_png(self):
        """PNG files start with the 8-byte PNG signature."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _detect_media_type(png_bytes) == "png"

    def test_detects_webp(self):
        """WebP files start with RIFF....WEBP."""
        webp_bytes = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert _detect_media_type(webp_bytes) == "webp"

    def test_defaults_to_jpeg_for_unknown(self):
        """Unknown formats default to JPEG."""
        unknown_bytes = b"\x00\x01\x02\x03" + b"\x00" * 100
        assert _detect_media_type(unknown_bytes) == "jpeg"


# --- extract_text_from_image tests ---


class TestExtractTextFromImage:
    """Tests for extract_text_from_image function."""

    def test_returns_empty_string_for_empty_bytes(self):
        """Empty input should return empty string without calling Bedrock."""
        result = extract_text_from_image(b"")
        assert result == ""

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_successful_text_extraction(self, mock_get_client):
        """Should return extracted text from Bedrock response."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": "SALE 50% OFF\nBuy Now\nTerms apply"}
                    ]
                }
            }
        }

        # Use JPEG magic bytes
        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        result = extract_text_from_image(image_bytes)

        assert result == "SALE 50% OFF\nBuy Now\nTerms apply"
        mock_client.converse.assert_called_once()

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_strips_whitespace_from_response(self, mock_get_client):
        """Should strip leading/trailing whitespace from extracted text."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "  Hello World  \n  "}]
                }
            }
        }

        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = extract_text_from_image(image_bytes)

        assert result == "Hello World"

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_handles_client_error_gracefully(self, mock_get_client):
        """Should return empty string on Bedrock ClientError."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Converse",
        )

        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = extract_text_from_image(image_bytes)

        assert result == ""

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_handles_unexpected_response_structure(self, mock_get_client):
        """Should return empty string if response structure is unexpected."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Missing expected keys
        mock_client.converse.return_value = {"output": {}}

        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = extract_text_from_image(image_bytes)

        assert result == ""

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_handles_generic_exception(self, mock_get_client):
        """Should return empty string on any unexpected exception."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.side_effect = RuntimeError("Connection lost")

        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = extract_text_from_image(image_bytes)

        assert result == ""

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_sends_correct_model_id(self, mock_get_client):
        """Should use amazon.nova-pro-v1:0 model ID."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Some text"}]
                }
            }
        }

        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        extract_text_from_image(image_bytes)

        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["modelId"] == "apac.amazon.nova-pro-v1:0"

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_sends_image_bytes_in_message(self, mock_get_client):
        """Should send raw image bytes in the message content."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Extracted"}]
                }
            }
        }

        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        extract_text_from_image(image_bytes)

        call_kwargs = mock_client.converse.call_args[1]
        messages = call_kwargs["messages"]
        content = messages[0]["content"]

        # First content block should be the image
        assert "image" in content[0]
        assert content[0]["image"]["source"]["bytes"] == image_bytes
        assert content[0]["image"]["format"] == "jpeg"

        # Second content block should be the OCR prompt text
        assert "text" in content[1]
        assert "Extract ALL text" in content[1]["text"]

    @patch("culture_compliance.services.ocr._get_bedrock_client")
    def test_detects_png_format_in_request(self, mock_get_client):
        """Should detect PNG format and pass it to the API."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "PNG text"}]
                }
            }
        }

        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        extract_text_from_image(png_bytes)

        call_kwargs = mock_client.converse.call_args[1]
        image_block = call_kwargs["messages"][0]["content"][0]["image"]
        assert image_block["format"] == "png"
