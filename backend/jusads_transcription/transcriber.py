"""
transcriber.py
──────────────
Uploads audio/video files to AWS S3, generates a text transcript using Amazon Transcribe,
and optionally extracts audio via ffmpeg first to minimize upload time.
"""

import json
import logging
import os
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import boto3

from jusads_text_compliance.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION_EMBED,
    TRANSCRIBE_S3_BUCKET,
)

logger = logging.getLogger(__name__)

# Initialize boto3 clients
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_EMBED,
)
s3_client = session.client("s3")
transcribe_client = session.client("transcribe")


class VideoTranscriber:
    """Handles audio extraction and transcription via AWS Transcribe."""

    def __init__(self, use_ffmpeg: bool = True):
        self.use_ffmpeg = use_ffmpeg
        if not TRANSCRIBE_S3_BUCKET:
            raise ValueError("TRANSCRIBE_S3_BUCKET is not set in .env")

    def _extract_audio(self, video_path: str) -> str:
        """Extract audio from video using ffmpeg to speed up upload."""
        logger.info("Extracting audio from %s...", video_path)
        temp_audio_path = tempfile.mktemp(suffix=".mp3")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", video_path,
                    "-vn",  # No video
                    "-acodec", "libmp3lame",
                    "-q:a", "5",  # Moderate quality is fine for speech
                    temp_audio_path
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Audio extracted to %s", temp_audio_path)
            return temp_audio_path
        except FileNotFoundError:
            logger.warning("ffmpeg not found in PATH. Skipping audio extraction.")
            return video_path
        except subprocess.CalledProcessError as e:
            logger.error("ffmpeg extraction failed: %s. Proceeding with original file.", e)
            return video_path

    def transcribe_media(self, file_path: str) -> str:
        """Upload media to S3, run AWS Transcribe, and return the text."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        upload_path = str(path)
        is_temp = False

        # If it's a video and ffmpeg is enabled, try extracting audio first
        if self.use_ffmpeg and path.suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"]:
            extracted_path = self._extract_audio(upload_path)
            if extracted_path != upload_path:
                upload_path = extracted_path
                is_temp = True

        # Unique IDs for AWS
        job_id = f"jusads-transcribe-{uuid.uuid4().hex[:8]}"
        s3_key = f"transcribe-temp/{job_id}{Path(upload_path).suffix}"
        s3_uri = f"s3://{TRANSCRIBE_S3_BUCKET}/{s3_key}"

        try:
            # 1. Upload to S3
            logger.info("Uploading %s to S3 bucket %s...", upload_path, TRANSCRIBE_S3_BUCKET)
            s3_client.upload_file(upload_path, TRANSCRIBE_S3_BUCKET, s3_key)
            logger.info("File uploaded to %s", s3_uri)

            # 2. Start Transcription Job
            logger.info("Starting AWS Transcribe job: %s", job_id)
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_id,
                Media={"MediaFileUri": s3_uri},
                IdentifyLanguage=True,  # Auto-detect language
            )

            # 3. Poll for Completion
            while True:
                response = transcribe_client.get_transcription_job(TranscriptionJobName=job_id)
                status = response["TranscriptionJob"]["TranscriptionJobStatus"]
                
                if status == "COMPLETED":
                    logger.info("Transcription job COMPLETED.")
                    transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                    break
                elif status == "FAILED":
                    failure_reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                    raise RuntimeError(f"AWS Transcribe job failed: {failure_reason}")
                
                logger.info("Waiting for transcription to complete... (status: %s)", status)
                time.sleep(5)

            # 4. Fetch and Parse JSON Result
            logger.info("Fetching transcript JSON from %s", transcript_uri)
            with urllib.request.urlopen(transcript_uri) as res:
                transcript_data = json.loads(res.read().decode('utf-8'))
                
            # Extract raw text from AWS Transcribe JSON structure
            transcript_text = transcript_data["results"]["transcripts"][0]["transcript"]
            return transcript_text

        except Exception as e:
            logger.error("Transcription failed: %s", str(e))
            raise e
            
        finally:
            # Cleanup S3 File
            logger.info("Cleaning up S3 object: %s", s3_key)
            try:
                s3_client.delete_object(Bucket=TRANSCRIBE_S3_BUCKET, Key=s3_key)
            except Exception as e:
                logger.warning("Failed to delete S3 object: %s", e)
                
            # Cleanup Transcribe Job
            logger.info("Cleaning up Transcribe job: %s", job_id)
            try:
                transcribe_client.delete_transcription_job(TranscriptionJobName=job_id)
            except Exception as e:
                logger.warning("Failed to delete Transcribe job: %s", e)
                
            # Cleanup local temp audio file
            if is_temp and os.path.exists(upload_path):
                os.remove(upload_path)
