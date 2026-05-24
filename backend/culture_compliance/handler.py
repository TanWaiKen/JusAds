"""AWS Lambda handler for the content compliance pipeline.

Parses API Gateway proxy events, routes synchronous requests (text/image)
and asynchronous requests (video), validates payload size, cleans up /tmp
files, and returns JSON responses with proper status codes.

Requirements: 8.1, 8.2, 8.3, 8.5, 8.6, 8.7, 11.7
"""

import glob
import json
import logging
import os
import time
import uuid
from typing import Any

import boto3
from pydantic import ValidationError

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
)
from culture_compliance.orchestrator import run_pipeline

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Constants ---

MAX_PAYLOAD_SIZE_BYTES = 1_048_576  # 1 MB (Requirement 11.7)
SYNC_TIMEOUT_SECONDS = 55  # Synchronous timeout for text/image (Requirement 8.6)
S3_RESULTS_BUCKET = os.environ.get("COMPLIANCE_RESULTS_BUCKET", "compliance-results")
LAMBDA_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")


def _cleanup_tmp() -> None:
    """Remove all temporary files from /tmp created during this invocation.

    Ensures stateless operation between Lambda invocations per Requirement 8.2.
    """
    tmp_patterns = ["/tmp/compliance_*", "/tmp/frame_*", "/tmp/video_*"]
    for pattern in tmp_patterns:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
            except OSError:
                pass


def _build_response(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy response.

    Args:
        status_code: HTTP status code.
        body: Response body dict to serialize as JSON.

    Returns:
        API Gateway proxy response dict with statusCode, headers, and body.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def _parse_event_body(event: dict) -> tuple[dict | None, dict | None]:
    """Parse the request body from an API Gateway proxy event.

    Validates payload size (max 1 MB) and parses JSON body.

    Args:
        event: API Gateway proxy event dict.

    Returns:
        Tuple of (parsed_body, error_response). If parsing succeeds,
        error_response is None. If parsing fails, parsed_body is None
        and error_response contains the appropriate HTTP response.
    """
    body_str = event.get("body", "")

    if body_str is None:
        return None, _build_response(400, {
            "error": "validation",
            "message": "Request body is required",
        })

    # Check payload size (Requirement 11.7)
    body_bytes = body_str.encode("utf-8") if isinstance(body_str, str) else body_str
    if len(body_bytes) > MAX_PAYLOAD_SIZE_BYTES:
        return None, _build_response(413, {
            "error": "payload_too_large",
            "message": (
                f"Request payload exceeds maximum allowed size of "
                f"{MAX_PAYLOAD_SIZE_BYTES} bytes (1 MB)"
            ),
        })

    # Parse JSON
    try:
        parsed = json.loads(body_str)
    except (json.JSONDecodeError, TypeError) as e:
        return None, _build_response(400, {
            "error": "validation",
            "message": f"Invalid JSON payload: {str(e)}",
        })

    if not isinstance(parsed, dict):
        return None, _build_response(400, {
            "error": "validation",
            "message": "Request body must be a JSON object",
        })

    return parsed, None


def _handle_sync_request(submission: ContentSubmission) -> dict:
    """Handle a synchronous compliance request (text or image).

    Runs the pipeline synchronously and returns the result directly.
    Implements timeout handling per Requirement 8.5.

    Args:
        submission: Validated ContentSubmission.

    Returns:
        API Gateway proxy response dict.
    """
    start_time = time.time()

    try:
        result = run_pipeline(submission)
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Check if this was a timeout
        if elapsed_ms >= SYNC_TIMEOUT_SECONDS * 1000:
            timeout_result = {
                "content_type": submission.content_type.value,
                "market": submission.market.value,
                "risk_level": "Unknown",
                "score": -1,
                "high_risk_indicators": [],
                "explanation": (
                    f"Pipeline execution timed out after {elapsed_ms}ms. "
                    f"Content routing completed but evaluation was not reached."
                ),
                "suggestion": "Please retry the submission or try with smaller content.",
                "processing_metadata": {
                    "pipeline_duration_ms": elapsed_ms,
                    "models_used": [],
                    "market": submission.market.value,
                },
                "warnings": [],
            }
            return _build_response(504, timeout_result)

        logger.error("Pipeline execution failed: %s", str(e))
        return _build_response(500, {
            "error": "internal_error",
            "message": f"Pipeline execution failed: {str(e)}",
        })

    # Successful result
    if isinstance(result, dict):
        return _build_response(200, result)
    else:
        # ComplianceResult object - serialize
        return _build_response(200, result.model_dump())


def _handle_async_request(submission: ContentSubmission, request_id: str) -> dict:
    """Handle an asynchronous compliance request (video).

    Invokes the pipeline asynchronously via Lambda self-invocation and
    stores the result in S3 at a predictable key (Requirement 8.7).

    Args:
        submission: Validated ContentSubmission.
        request_id: Unique request identifier for result retrieval.

    Returns:
        API Gateway proxy response dict with accepted status and result location.
    """
    # Build the S3 result key
    result_key = f"results/{request_id}.json"

    try:
        # Invoke self asynchronously with the submission
        lambda_client = boto3.client("lambda")
        async_payload = {
            "async_execution": True,
            "request_id": request_id,
            "result_bucket": S3_RESULTS_BUCKET,
            "result_key": result_key,
            "submission": submission.model_dump(),
        }

        lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="Event",  # Asynchronous invocation
            Payload=json.dumps(async_payload).encode("utf-8"),
        )
    except Exception as e:
        logger.error("Failed to invoke async Lambda: %s", str(e))
        return _build_response(500, {
            "error": "internal_error",
            "message": f"Failed to initiate async processing: {str(e)}",
        })

    return _build_response(202, {
        "message": "Video compliance evaluation accepted for processing",
        "request_id": request_id,
        "result_location": f"s3://{S3_RESULTS_BUCKET}/{result_key}",
    })


def _execute_async_pipeline(event: dict) -> dict:
    """Execute the pipeline for an async invocation and store result in S3.

    Called when the Lambda is invoked asynchronously for video processing.

    Args:
        event: Async invocation event containing submission data and S3 location.

    Returns:
        API Gateway proxy response dict (for logging purposes).
    """
    request_id = event.get("request_id", "unknown")
    result_bucket = event.get("result_bucket", S3_RESULTS_BUCKET)
    result_key = event.get("result_key", f"results/{request_id}.json")
    submission_data = event.get("submission", {})

    try:
        # Reconstruct the submission
        # Convert enum values back for Pydantic
        if "content_type" in submission_data and isinstance(
            submission_data["content_type"], str
        ):
            pass  # Pydantic handles string-to-enum conversion
        if "market" in submission_data and isinstance(
            submission_data["market"], str
        ):
            pass  # Pydantic handles string-to-enum conversion

        submission = ContentSubmission(**submission_data)
        result = run_pipeline(submission)

        # Serialize result
        if isinstance(result, dict):
            result_json = json.dumps(result, ensure_ascii=False)
        else:
            result_json = json.dumps(result.model_dump(), ensure_ascii=False)

        # Store in S3
        s3_client = boto3.client("s3")
        s3_client.put_object(
            Bucket=result_bucket,
            Key=result_key,
            Body=result_json.encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )

        logger.info(
            "Async pipeline completed for request %s. Result stored at s3://%s/%s",
            request_id,
            result_bucket,
            result_key,
        )

        return _build_response(200, {"message": "Async processing completed"})

    except Exception as e:
        logger.error(
            "Async pipeline failed for request %s: %s", request_id, str(e)
        )

        # Store error result in S3 so the client can retrieve it
        error_result = {
            "error": "pipeline_error",
            "message": str(e),
            "request_id": request_id,
        }
        try:
            s3_client = boto3.client("s3")
            s3_client.put_object(
                Bucket=result_bucket,
                Key=result_key,
                Body=json.dumps(error_result).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )
        except Exception as s3_err:
            logger.error("Failed to store error result in S3: %s", str(s3_err))

        return _build_response(500, error_result)


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the content compliance pipeline.

    Parses API Gateway proxy events, validates payload size, routes
    synchronous (text/image) and asynchronous (video) requests, and
    returns JSON responses with proper status codes.

    Args:
        event: API Gateway proxy event or async invocation event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict with statusCode, headers, and body.
    """
    try:
        # Check if this is an async execution (self-invoked for video)
        if event.get("async_execution"):
            response = _execute_async_pipeline(event)
            _cleanup_tmp()
            return response

        # Handle CORS preflight
        http_method = event.get("httpMethod", "")
        if http_method == "OPTIONS":
            return _build_response(200, {})

        # Parse and validate the request body
        parsed_body, error_response = _parse_event_body(event)
        if error_response:
            return error_response

        # Validate the submission using Pydantic
        try:
            submission = ContentSubmission(**parsed_body)
        except ValidationError as e:
            error_details = []
            for err in e.errors():
                error_details.append({
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                })
            return _build_response(400, {
                "error": "validation",
                "message": "Invalid submission",
                "details": error_details,
            })

        # Generate a request ID for tracking
        request_id = str(uuid.uuid4())

        # Route based on content type
        if submission.content_type == ContentType.VIDEO:
            # Video: invoke asynchronously (Requirement 8.7)
            response = _handle_async_request(submission, request_id)
        else:
            # Text/Image: process synchronously (Requirement 8.6)
            response = _handle_sync_request(submission)

        return response

    except Exception as e:
        logger.error("Unhandled error in lambda_handler: %s", str(e))
        return _build_response(500, {
            "error": "internal_error",
            "message": "An unexpected error occurred",
        })

    finally:
        # Always clean up /tmp files (Requirement 8.2)
        _cleanup_tmp()
