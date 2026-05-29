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
import urllib.request
import uuid
from pathlib import Path

import boto3

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION_EMBED,
    TRANSCRIBE_S3_BUCKET,
)

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_EMBED,
)
s3_client = session.client("s3")
transcribe_client = session.client("transcribe")

