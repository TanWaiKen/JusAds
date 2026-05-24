"""Audio transcription service using Amazon Transcribe.

Extracts audio from video files using ffmpeg, uploads to S3, and uses
Amazon Transcribe to produce segment-level timestamped transcripts.

Requirements: 4.2, 4.9, 4.10
"""

import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import AWS_REGION_LLM, TRANSCRIBE_S3_BUCKET

logger = logging.getLogger(__name__)

# Configuration
_S3_BUCKET = TRANSCRIBE_S3_BUCKET
_S3_PREFIX = os.environ.get("TRANSCRIBE_S3_PREFIX", "transcribe-audio/")
_LANGUAGE_CODE = os.environ.get("TRANSCRIBE_LANGUAGE_CODE", "en-US")
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_ATTEMPTS = 120  # 10 minutes max wait

# Boto3 client configuration with retry logic
_client_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    }
)


def _get_transcribe_client():
    """Create an Amazon Transcribe client.

    Separated for testability — allows mocking in unit tests.
    """
    return boto3.client(
        "transcribe",
        region_name=AWS_REGION_LLM,
        config=_client_config,
    )


def _get_s3_client():
    """Create an S3 client.

    Separated for testability — allows mocking in unit tests.
    """
    return boto3.client(
        "s3",
        region_name=AWS_REGION_LLM,
        config=_client_config,
    )


def _extract_audio(video_path: str, output_path: str) -> bool:
    """Extract audio track from a video file using ffmpeg.

    Args:
        video_path: Path to the input video file.
        output_path: Path where the extracted audio file will be written.

    Returns:
        True if audio was successfully extracted, False if the video
        has no audio track or extraction failed.
    """
    try:
        # First, check if the video has an audio stream
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            video_path,
        ]

        probe_result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # If no audio stream found, return False
        if not probe_result.stdout.strip():
            logger.info("No audio track found in video: %s", video_path)
            return False

        # Extract audio to WAV format (Amazon Transcribe supports wav, mp3, mp4, flac)
        extract_cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # PCM 16-bit little-endian
            "-ar", "16000",  # 16kHz sample rate (optimal for speech)
            "-ac", "1",  # Mono channel
            "-y",  # Overwrite output
            output_path,
        ]

        result = subprocess.run(
            extract_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(
                "ffmpeg audio extraction failed (returncode=%d): %s",
                result.returncode,
                result.stderr[:500],
            )
            return False

        # Verify the output file exists and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error("Audio extraction produced empty or missing file")
            return False

        logger.info(
            "Audio extracted successfully: %s (size=%d bytes)",
            output_path,
            os.path.getsize(output_path),
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error("Audio extraction timed out for: %s", video_path)
        return False
    except FileNotFoundError:
        logger.error(
            "ffmpeg/ffprobe not found. Ensure ffmpeg is installed and on PATH."
        )
        return False
    except Exception as e:
        logger.error("Unexpected error during audio extraction: %s", str(e))
        return False


def _upload_to_s3(local_path: str, s3_key: str) -> str:
    """Upload a local file to S3.

    Args:
        local_path: Path to the local file.
        s3_key: S3 object key for the upload.

    Returns:
        The S3 URI (s3://bucket/key) of the uploaded file.

    Raises:
        ClientError: If the upload fails.
    """
    s3_client = _get_s3_client()
    s3_client.upload_file(local_path, _S3_BUCKET, s3_key)
    s3_uri = f"s3://{_S3_BUCKET}/{s3_key}"
    logger.info("Uploaded audio to S3: %s", s3_uri)
    return s3_uri


def _start_transcription_job(s3_uri: str, job_name: str) -> str:
    """Start an Amazon Transcribe batch job.

    Args:
        s3_uri: S3 URI of the audio file.
        job_name: Unique name for the transcription job.

    Returns:
        The job name (used for polling).

    Raises:
        ClientError: If the job cannot be started.
    """
    client = _get_transcribe_client()

    client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": s3_uri},
        MediaFormat="wav",
        LanguageCode=_LANGUAGE_CODE,
        Settings={
            "ShowSpeakerLabels": False,
            "ShowAlternatives": False,
        },
    )

    logger.info("Started transcription job: %s", job_name)
    return job_name


def _wait_for_job(job_name: str) -> dict | None:
    """Poll Amazon Transcribe until the job completes or fails.

    Args:
        job_name: The transcription job name to poll.

    Returns:
        The transcription job result dict if completed, None if failed or timed out.
    """
    client = _get_transcribe_client()

    for attempt in range(_MAX_POLL_ATTEMPTS):
        response = client.get_transcription_job(
            TranscriptionJobName=job_name,
        )
        job = response["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]

        if status == "COMPLETED":
            logger.info(
                "Transcription job completed: %s (attempt %d)",
                job_name,
                attempt + 1,
            )
            return job

        if status == "FAILED":
            failure_reason = job.get("FailureReason", "Unknown reason")
            logger.error(
                "Transcription job failed: %s - %s", job_name, failure_reason
            )
            return None

        # Still in progress, wait before polling again
        time.sleep(_POLL_INTERVAL_SECONDS)

    logger.error(
        "Transcription job timed out after %d attempts: %s",
        _MAX_POLL_ATTEMPTS,
        job_name,
    )
    return None


def _parse_transcript_results(job: dict) -> list[dict]:
    """Parse Amazon Transcribe results into segment-level timestamps.

    Downloads the transcript JSON from the URI provided in the job result
    and extracts segment-level timestamps.

    Args:
        job: The completed transcription job dict from Amazon Transcribe.

    Returns:
        List of dicts with keys: start_time (float), end_time (float), text (str).
    """
    try:
        transcript_uri = job["Transcript"]["TranscriptFileUri"]

        # Download the transcript JSON
        # The URI is an HTTPS URL that we can fetch with boto3's S3 client
        # or use requests. For simplicity, use boto3 to get the object
        # if it's in our bucket, or use the JSON directly from the API.
        import urllib.request

        with urllib.request.urlopen(transcript_uri) as response:
            transcript_data = json.loads(response.read().decode("utf-8"))

        # Parse items into segments
        segments = _items_to_segments(transcript_data)
        logger.info("Parsed %d transcript segments", len(segments))
        return segments

    except Exception as e:
        logger.error("Failed to parse transcript results: %s", str(e))
        return []


def _items_to_segments(transcript_data: dict) -> list[dict]:
    """Convert Amazon Transcribe items into coherent text segments.

    Amazon Transcribe returns word-level items. This function groups them
    into sentence-like segments based on punctuation and pauses.

    Args:
        transcript_data: The full transcript JSON from Amazon Transcribe.

    Returns:
        List of segment dicts with start_time, end_time, and text.
    """
    segments = []
    items = transcript_data.get("results", {}).get("items", [])

    if not items:
        return segments

    current_segment_start = None
    current_segment_end = None
    current_words: list[str] = []

    for item in items:
        item_type = item.get("type", "")
        content = item.get("alternatives", [{}])[0].get("content", "")

        if item_type == "pronunciation":
            start = float(item.get("start_time", 0))
            end = float(item.get("end_time", 0))

            if current_segment_start is None:
                current_segment_start = start

            current_segment_end = end
            current_words.append(content)

        elif item_type == "punctuation":
            # Punctuation marks the end of a segment
            current_words.append(content)

            if current_segment_start is not None and current_words:
                segment_text = " ".join(current_words)
                # Fix spacing before punctuation
                segment_text = segment_text.replace(" .", ".")
                segment_text = segment_text.replace(" ,", ",")
                segment_text = segment_text.replace(" ?", "?")
                segment_text = segment_text.replace(" !", "!")

                segments.append({
                    "start_time": current_segment_start,
                    "end_time": current_segment_end,
                    "text": segment_text,
                })

                # Reset for next segment
                current_segment_start = None
                current_segment_end = None
                current_words = []

    # Handle any remaining words without trailing punctuation
    if current_words and current_segment_start is not None:
        segments.append({
            "start_time": current_segment_start,
            "end_time": current_segment_end,
            "text": " ".join(current_words),
        })

    return segments


def _cleanup_s3(s3_key: str) -> None:
    """Delete a temporary file from S3.

    Args:
        s3_key: The S3 object key to delete.
    """
    try:
        s3_client = _get_s3_client()
        s3_client.delete_object(Bucket=_S3_BUCKET, Key=s3_key)
        logger.info("Cleaned up S3 object: s3://%s/%s", _S3_BUCKET, s3_key)
    except Exception as e:
        logger.warning("Failed to clean up S3 object %s: %s", s3_key, str(e))


def _cleanup_transcription_job(job_name: str) -> None:
    """Delete a completed transcription job.

    Args:
        job_name: The transcription job name to delete.
    """
    try:
        client = _get_transcribe_client()
        client.delete_transcription_job(TranscriptionJobName=job_name)
        logger.info("Cleaned up transcription job: %s", job_name)
    except Exception as e:
        logger.warning("Failed to clean up transcription job %s: %s", job_name, str(e))


def transcribe_audio(video_path: str) -> list[dict]:
    """Transcribe audio from a video file using Amazon Transcribe.

    Extracts the audio track from the video, uploads it to S3, runs an
    Amazon Transcribe batch job, and returns segment-level timestamps.

    Args:
        video_path: Path to the video file on the local filesystem.

    Returns:
        List of transcript segments, each containing:
            - start_time (float): Segment start time in seconds
            - end_time (float): Segment end time in seconds
            - text (str): Transcribed text for the segment

        Returns an empty list if:
            - The video has no audio track (Requirement 4.9)
            - Transcription fails for any reason (Requirement 4.10)

    Requirements:
        4.2 - Extract and transcribe audio with segment-level timestamps
        4.9 - Handle videos with no audio track (return empty list)
        4.10 - Handle transcription failures gracefully
    """
    if not video_path:
        logger.warning("Empty video path provided to transcribe_audio")
        return []

    if not os.path.exists(video_path):
        logger.error("Video file not found: %s", video_path)
        return []

    # Generate unique identifiers for this transcription
    unique_id = uuid.uuid4().hex[:12]
    job_name = f"langhub-transcribe-{unique_id}"
    s3_key = f"{_S3_PREFIX}{unique_id}.wav"
    audio_temp_path = None

    try:
        # Step 1: Extract audio from video to a temporary file
        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="langhub_audio_"
        ) as tmp_file:
            audio_temp_path = tmp_file.name

        has_audio = _extract_audio(video_path, audio_temp_path)

        if not has_audio:
            # Requirement 4.9: No audio track — return empty list
            logger.info("Video has no audio track, skipping transcription")
            return []

        # Step 2: Upload audio to S3
        s3_uri = _upload_to_s3(audio_temp_path, s3_key)

        # Step 3: Start transcription job
        _start_transcription_job(s3_uri, job_name)

        # Step 4: Wait for job completion
        job_result = _wait_for_job(job_name)

        if job_result is None:
            # Requirement 4.10: Transcription failed — return empty list
            logger.warning(
                "Transcription job did not complete successfully for: %s",
                video_path,
            )
            return []

        # Step 5: Parse transcript results into segments
        segments = _parse_transcript_results(job_result)
        return segments

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(
            "AWS service error during transcription: %s - %s",
            error_code,
            str(e),
        )
        return []

    except Exception as e:
        # Requirement 4.10: Handle all failures gracefully
        logger.error(
            "Unexpected error during audio transcription: %s", str(e)
        )
        return []

    finally:
        # Step 6: Clean up temporary files
        if audio_temp_path and os.path.exists(audio_temp_path):
            try:
                os.unlink(audio_temp_path)
                logger.debug("Cleaned up temp audio file: %s", audio_temp_path)
            except OSError as e:
                logger.warning(
                    "Failed to clean up temp file %s: %s", audio_temp_path, str(e)
                )

        # Clean up S3 and transcription job (best effort)
        _cleanup_s3(s3_key)
        _cleanup_transcription_job(job_name)
