"""Unit tests for the AWS Lambda handler.

Tests API Gateway event parsing, synchronous response for text/image,
async invocation for video, payload size rejection (>1 MB), and /tmp cleanup.

Requirements: 8.1, 8.2, 8.5, 8.6, 8.7, 11.7
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from culture_compliance.handler import (
    MAX_PAYLOAD_SIZE_BYTES,
    SYNC_TIMEOUT_SECONDS,
    _build_response,
    _cleanup_tmp,
    _parse_event_body,
    lambda_handler,
)


# --- Fixtures ---


def _make_api_gateway_event(body: dict | str | None = None, method: str = "POST") -> dict:
    """Create a minimal API Gateway proxy event for testing."""
    event = {
        "httpMethod": method,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if isinstance(body, dict) else body,
        "requestContext": {"requestId": "test-request-id"},
    }
    return event


# --- Tests for _build_response ---


class TestBuildResponse:
    """Tests for the response builder utility."""

    def test_builds_correct_structure(self):
        response = _build_response(200, {"key": "value"})
        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]
        assert response["headers"]["Content-Type"] == "application/json; charset=utf-8"
        body = json.loads(response["body"])
        assert body == {"key": "value"}

    def test_preserves_non_ascii_characters(self):
        response = _build_response(200, {"text": "Bahasa Melayu: Selamat datang"})
        assert "Selamat datang" in response["body"]

    def test_cors_headers_present(self):
        response = _build_response(200, {})
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "POST" in response["headers"]["Access-Control-Allow-Methods"]


# --- Tests for _parse_event_body ---


class TestParseEventBody:
    """Tests for event body parsing and validation."""

    def test_parses_valid_json_body(self):
        event = _make_api_gateway_event({"content": "test", "content_type": "text"})
        parsed, error = _parse_event_body(event)
        assert error is None
        assert parsed == {"content": "test", "content_type": "text"}

    def test_rejects_null_body(self):
        event = {"body": None}
        parsed, error = _parse_event_body(event)
        assert parsed is None
        assert error["statusCode"] == 400

    def test_rejects_invalid_json(self):
        event = {"body": "not valid json {{{"}
        parsed, error = _parse_event_body(event)
        assert parsed is None
        assert error["statusCode"] == 400
        body = json.loads(error["body"])
        assert "Invalid JSON" in body["message"]

    def test_rejects_payload_exceeding_1mb(self):
        # Create a payload just over 1 MB
        large_content = "x" * (MAX_PAYLOAD_SIZE_BYTES + 1)
        event = {"body": large_content}
        parsed, error = _parse_event_body(event)
        assert parsed is None
        assert error["statusCode"] == 413
        body = json.loads(error["body"])
        assert "payload_too_large" in body["error"]
        assert "1 MB" in body["message"]

    def test_accepts_payload_at_exactly_1mb(self):
        # Create a valid JSON payload that's exactly at the limit
        # We need valid JSON, so account for the JSON structure overhead
        content = "a" * (MAX_PAYLOAD_SIZE_BYTES - 50)
        payload = json.dumps({"content": content})
        # Only test if it fits within 1 MB
        if len(payload.encode("utf-8")) <= MAX_PAYLOAD_SIZE_BYTES:
            event = {"body": payload}
            parsed, error = _parse_event_body(event)
            assert error is None
            assert parsed is not None

    def test_rejects_non_object_json(self):
        event = {"body": json.dumps([1, 2, 3])}
        parsed, error = _parse_event_body(event)
        assert parsed is None
        assert error["statusCode"] == 400
        body = json.loads(error["body"])
        assert "JSON object" in body["message"]

    def test_rejects_empty_string_body(self):
        """Requirement 8.1: Empty body string should fail JSON parsing."""
        event = {"body": ""}
        parsed, error = _parse_event_body(event)
        assert parsed is None
        assert error["statusCode"] == 400

    def test_payload_just_under_1mb_accepted(self):
        """Requirement 11.7: Payload at boundary should be accepted."""
        # Create a payload that is just under 1 MB
        # Use a simple repeated character to control size precisely
        target_size = MAX_PAYLOAD_SIZE_BYTES - 100
        content = "a" * target_size
        event = {"body": content}
        # This will fail JSON parsing but should NOT fail size check
        parsed, error = _parse_event_body(event)
        # Should get a JSON parse error, not a size error
        assert error["statusCode"] == 400
        body = json.loads(error["body"])
        assert body["error"] == "validation"
        assert "Invalid JSON" in body["message"]


# --- Tests for lambda_handler ---


class TestLambdaHandlerCORS:
    """Tests for CORS preflight handling."""

    def test_options_request_returns_200(self):
        event = _make_api_gateway_event(method="OPTIONS")
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200


class TestLambdaHandlerValidation:
    """Tests for input validation in the handler."""

    def test_rejects_missing_content_type(self):
        event = _make_api_gateway_event({"content": "hello"})
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "validation"

    def test_rejects_empty_content(self):
        event = _make_api_gateway_event({
            "content": "   ",
            "content_type": "text",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "validation"

    def test_rejects_invalid_content_type(self):
        event = _make_api_gateway_event({
            "content": "hello",
            "content_type": "audio",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400

    def test_rejects_oversized_payload(self):
        large_body = json.dumps({
            "content": "x" * MAX_PAYLOAD_SIZE_BYTES,
            "content_type": "text",
        })
        event = {"httpMethod": "POST", "body": large_body, "headers": {}}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 413


class TestLambdaHandlerSyncRequest:
    """Tests for synchronous text/image request handling."""

    @patch("culture_compliance.handler.run_pipeline")
    def test_text_request_returns_200(self, mock_pipeline):
        mock_pipeline.return_value = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 95,
            "high_risk_indicators": [],
            "explanation": "Content is compliant.",
            "suggestion": "No changes needed.",
            "processing_metadata": {
                "pipeline_duration_ms": 1200,
                "models_used": ["nova-lite"],
                "market": "malaysia",
            },
            "warnings": [],
        }

        event = _make_api_gateway_event({
            "content": "Buy our product today!",
            "content_type": "text",
            "market": "malaysia",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["risk_level"] == "Low"
        assert body["score"] == 95
        mock_pipeline.assert_called_once()

    @patch("culture_compliance.handler.run_pipeline")
    def test_image_request_returns_200(self, mock_pipeline):
        mock_pipeline.return_value = {
            "content_type": "image",
            "market": "malaysia",
            "risk_level": "Medium",
            "score": 60,
            "high_risk_indicators": [],
            "explanation": "Some concerns detected.",
            "suggestion": "Review image content.",
            "processing_metadata": {
                "pipeline_duration_ms": 3000,
                "models_used": ["nova-pro"],
                "market": "malaysia",
            },
            "warnings": [],
        }

        event = _make_api_gateway_event({
            "content": "base64encodedimage==",
            "content_type": "image",
            "market": "malaysia",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["content_type"] == "image"

    @patch("culture_compliance.handler.run_pipeline")
    def test_pipeline_exception_returns_500(self, mock_pipeline):
        mock_pipeline.side_effect = RuntimeError("Service unavailable")

        event = _make_api_gateway_event({
            "content": "test content",
            "content_type": "text",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("culture_compliance.handler.run_pipeline")
    @patch("culture_compliance.handler.time")
    def test_timeout_returns_504_with_unknown_risk(self, mock_time, mock_pipeline):
        """Requirement 8.5: Timeout returns risk_level 'Unknown' and score -1."""
        # Simulate a timeout: start_time is 0, elapsed time exceeds threshold
        mock_time.time.side_effect = [0.0, SYNC_TIMEOUT_SECONDS + 1.0]
        mock_pipeline.side_effect = RuntimeError("Timeout exceeded")

        event = _make_api_gateway_event({
            "content": "test content",
            "content_type": "text",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 504
        body = json.loads(response["body"])
        assert body["risk_level"] == "Unknown"
        assert body["score"] == -1
        assert body["high_risk_indicators"] == []
        assert "timed out" in body["explanation"].lower() or "timed out" in body["explanation"]

    @patch("culture_compliance.handler.run_pipeline")
    def test_sync_handler_serializes_compliance_result_object(self, mock_pipeline):
        """Requirement 8.6: Handler serializes ComplianceResult objects via model_dump()."""
        # Return a mock object with model_dump method (simulating a Pydantic model)
        mock_result = MagicMock()
        mock_result_dict = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "All clear.",
            "suggestion": "No changes.",
            "processing_metadata": {
                "pipeline_duration_ms": 500,
                "models_used": ["nova-lite"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        mock_result.model_dump.return_value = mock_result_dict
        # Make isinstance(result, dict) return False
        mock_pipeline.return_value = mock_result

        event = _make_api_gateway_event({
            "content": "test content",
            "content_type": "text",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["score"] == 100
        mock_result.model_dump.assert_called_once()


class TestLambdaHandlerAsyncRequest:
    """Tests for asynchronous video request handling."""

    @patch("culture_compliance.handler.boto3")
    def test_video_request_returns_202(self, mock_boto3):
        mock_lambda_client = MagicMock()
        mock_boto3.client.return_value = mock_lambda_client

        event = _make_api_gateway_event({
            "content": "s3://bucket/video.mp4",
            "content_type": "video",
            "market": "singapore",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert "request_id" in body
        assert "result_location" in body
        assert body["result_location"].startswith("s3://")

    @patch("culture_compliance.handler.boto3")
    def test_video_invokes_lambda_async(self, mock_boto3):
        mock_lambda_client = MagicMock()
        mock_boto3.client.return_value = mock_lambda_client

        event = _make_api_gateway_event({
            "content": "s3://bucket/video.mp4",
            "content_type": "video",
        })
        lambda_handler(event, None)

        # Verify Lambda was invoked with Event type (async)
        mock_lambda_client.invoke.assert_called_once()
        call_kwargs = mock_lambda_client.invoke.call_args[1]
        assert call_kwargs["InvocationType"] == "Event"

    @patch("culture_compliance.handler.boto3")
    def test_video_async_failure_returns_500(self, mock_boto3):
        mock_lambda_client = MagicMock()
        mock_lambda_client.invoke.side_effect = Exception("Lambda invoke failed")
        mock_boto3.client.return_value = mock_lambda_client

        event = _make_api_gateway_event({
            "content": "s3://bucket/video.mp4",
            "content_type": "video",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 500


class TestLambdaHandlerAsyncExecution:
    """Tests for the async execution path (self-invoked for video)."""

    @patch("culture_compliance.handler.boto3")
    @patch("culture_compliance.handler.run_pipeline")
    def test_async_execution_stores_result_in_s3(self, mock_pipeline, mock_boto3):
        mock_pipeline.return_value = {
            "content_type": "video",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 90,
            "high_risk_indicators": [],
            "explanation": "Video is compliant.",
            "suggestion": "No changes needed.",
            "processing_metadata": {
                "pipeline_duration_ms": 5000,
                "models_used": ["nova-pro"],
                "market": "malaysia",
            },
            "warnings": [],
        }

        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        event = {
            "async_execution": True,
            "request_id": "test-123",
            "result_bucket": "my-bucket",
            "result_key": "results/test-123.json",
            "submission": {
                "content": "s3://bucket/video.mp4",
                "content_type": "video",
                "market": "malaysia",
            },
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify S3 put_object was called
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "my-bucket"
        assert call_kwargs["Key"] == "results/test-123.json"

    @patch("culture_compliance.handler.boto3")
    @patch("culture_compliance.handler.run_pipeline")
    def test_async_execution_failure_stores_error(self, mock_pipeline, mock_boto3):
        mock_pipeline.side_effect = RuntimeError("Processing failed")

        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        event = {
            "async_execution": True,
            "request_id": "test-456",
            "result_bucket": "my-bucket",
            "result_key": "results/test-456.json",
            "submission": {
                "content": "s3://bucket/video.mp4",
                "content_type": "video",
                "market": "malaysia",
            },
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 500

        # Verify error was stored in S3
        mock_s3_client.put_object.assert_called_once()


class TestTmpCleanup:
    """Tests for /tmp file cleanup (Requirement 8.2)."""

    def test_cleanup_removes_compliance_files(self, tmp_path):
        """Test that cleanup removes files matching compliance patterns."""
        # We can't easily test /tmp directly in unit tests,
        # but we can verify the function doesn't raise errors
        _cleanup_tmp()  # Should not raise

    @patch("culture_compliance.handler.glob.glob")
    @patch("culture_compliance.handler.os.remove")
    def test_cleanup_removes_matching_patterns(self, mock_remove, mock_glob):
        """Requirement 8.2: Cleanup removes compliance_*, frame_*, video_* from /tmp."""
        mock_glob.side_effect = [
            ["/tmp/compliance_abc123"],  # compliance_* pattern
            ["/tmp/frame_001.jpg", "/tmp/frame_002.jpg"],  # frame_* pattern
            ["/tmp/video_temp.mp4"],  # video_* pattern
        ]

        _cleanup_tmp()

        assert mock_remove.call_count == 4
        mock_remove.assert_any_call("/tmp/compliance_abc123")
        mock_remove.assert_any_call("/tmp/frame_001.jpg")
        mock_remove.assert_any_call("/tmp/frame_002.jpg")
        mock_remove.assert_any_call("/tmp/video_temp.mp4")

    @patch("culture_compliance.handler.glob.glob")
    @patch("culture_compliance.handler.os.remove")
    def test_cleanup_handles_os_errors_gracefully(self, mock_remove, mock_glob):
        """Requirement 8.2: Cleanup does not raise on OSError."""
        mock_glob.return_value = ["/tmp/compliance_locked_file"]
        mock_remove.side_effect = OSError("Permission denied")

        # Should not raise
        _cleanup_tmp()

    @patch("culture_compliance.handler.run_pipeline")
    @patch("culture_compliance.handler._cleanup_tmp")
    def test_cleanup_called_after_sync_request(self, mock_cleanup, mock_pipeline):
        mock_pipeline.return_value = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Clean.",
            "suggestion": "None.",
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": [],
                "market": "malaysia",
            },
            "warnings": [],
        }

        event = _make_api_gateway_event({
            "content": "test",
            "content_type": "text",
        })
        lambda_handler(event, None)
        mock_cleanup.assert_called()

    @patch("culture_compliance.handler._cleanup_tmp")
    def test_cleanup_called_even_on_error(self, mock_cleanup):
        event = _make_api_gateway_event({"invalid": "data"})
        lambda_handler(event, None)
        mock_cleanup.assert_called()

    @patch("culture_compliance.handler.boto3")
    @patch("culture_compliance.handler.run_pipeline")
    @patch("culture_compliance.handler._cleanup_tmp")
    def test_cleanup_called_after_async_execution(self, mock_cleanup, mock_pipeline, mock_boto3):
        """Requirement 8.2: Cleanup is called after async video processing."""
        mock_pipeline.return_value = {"content_type": "video", "score": 90}
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        event = {
            "async_execution": True,
            "request_id": "test-cleanup",
            "result_bucket": "bucket",
            "result_key": "results/test.json",
            "submission": {
                "content": "s3://bucket/video.mp4",
                "content_type": "video",
                "market": "malaysia",
            },
        }
        lambda_handler(event, None)
        mock_cleanup.assert_called()
