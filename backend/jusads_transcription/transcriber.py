"""
transcriber.py
──────────────
Extracts audio from video files and transcribes via AWS Transcribe.
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

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    TRANSCRIBE_S3_BUCKET,
)

logger = logging.getLogger(__name__)

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)
s3_client = session.client("s3")
transcribe_client = session.client("transcribe")


class Transcriber:
    """Handles audio extraction and transcription via AWS Transcribe."""

    def __init__(self):
        if not TRANSCRIBE_S3_BUCKET:
            raise ValueError("TRANSCRIBE_S3_BUCKET is not set in config")

    def extract_audio(self, video_path: str) -> str:
        """Extract audio from video using ffmpeg."""
        logger.info(f"Extracting audio from {video_path}")
        temp_audio_path = tempfile.mktemp(suffix=".mp3")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-q:a", "5",
                temp_audio_path
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return temp_audio_path

    def transcribe_media(self, file_path: str) -> str:
        """Upload media to S3, run AWS Transcribe, and return the text."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        upload_path = str(path)
        is_temp = False

        if path.suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"]:
            upload_path = self.extract_audio(upload_path)
            is_temp = True

        job_id = f"jusads-{uuid.uuid4().hex[:8]}"
        s3_key = f"transcribe-temp/{job_id}{Path(upload_path).suffix}"
        s3_uri = f"s3://{TRANSCRIBE_S3_BUCKET}/{s3_key}"

        try:
            logger.info(f"Uploading to {s3_uri}")
            s3_client.upload_file(upload_path, TRANSCRIBE_S3_BUCKET, s3_key)

            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_id,
                Media={"MediaFileUri": s3_uri},
                IdentifyLanguage=True,
            )

            while True:
                response = transcribe_client.get_transcription_job(TranscriptionJobName=job_id)
                status = response["TranscriptionJob"]["TranscriptionJobStatus"]
                
                if status == "COMPLETED":
                    transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                    break
                elif status == "FAILED":
                    reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                    raise RuntimeError(f"AWS Transcribe failed: {reason}")
                
                time.sleep(5)

            with urllib.request.urlopen(transcript_uri) as res:
                transcript_data = json.loads(res.read().decode('utf-8'))
                
            return transcript_data["results"]["transcripts"][0]["transcript"]

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise e
            
        finally:
            try:
                s3_client.delete_object(Bucket=TRANSCRIBE_S3_BUCKET, Key=s3_key)
                transcribe_client.delete_transcription_job(TranscriptionJobName=job_id)
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                
            if is_temp and os.path.exists(upload_path):
                os.remove(upload_path)
