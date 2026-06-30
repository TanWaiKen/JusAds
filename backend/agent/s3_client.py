"""
s3_client.py
────────────
Backward-compatibility shim. Use agent.s3_utils instead.
"""

import logging
from urllib.parse import quote

from botocore.exceptions import ClientError

from agent.clients import s3
from config import AWS_REGION, S3_BUCKET_NAME

logger = logging.getLogger(__name__)

BUCKET = S3_BUCKET_NAME
REGION = AWS_REGION



class S3MediaClient:
    """Legacy class wrapper — prefer using s3_utils functions directly."""

    def __init__(self, bucket_name=None, region=None):
        pass

    def upload_file(self, file_path, s3_key):
        return upload_file(file_path, s3_key)

    def get_public_url(self, s3_key):
        return get_public_url(s3_key)

    def upload_file_public(self, file_path, s3_key):
        return upload_file_public(file_path, s3_key)

    def generate_presigned_url(self, s3_key, expiry_seconds=3600):
        return generate_presigned_url(s3_key, expiry_seconds)

    def get_user_storage_usage(self, username):
        return get_user_storage_usage(username)

    def check_quota(self, username, file_size, max_bytes=5 * 1024**3):
        return check_quota(username, file_size, max_bytes)



def build_s3_key(
    asset_type: str,
    username: str,
    project_id: str,
    check_id: str,
    filename: str,
) -> str:
    """Construct an S3 object key.

    asset_type: "upload" | "remixed" | "segmented"
    Returns: e.g. uploads/{username}/{project_id}/{check_id}/{filename}
    """
    prefix_map = {"upload": "uploads", "remixed": "remixed", "segmented": "segmented"}
    prefix = prefix_map.get(asset_type)
    if prefix is None:
        raise ValueError(
            f"Invalid asset_type '{asset_type}'. Must be 'upload', 'remixed', or 'segmented'."
        )
    return f"{prefix}/{username}/{project_id}/{check_id}/{filename}"


def get_public_url(s3_key: str) -> str:
    """Return the public HTTPS URL for an S3 object (URL-encoded path)."""
    encoded_key = "/".join(quote(segment, safe="") for segment in s3_key.split("/"))
    return f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{encoded_key}"


# ─── Upload ───────────────────────────────────────────────────────────────────


def upload_file(file_path: str, s3_key: str) -> str:
    """Upload a local file to S3.

    Returns the S3 key on success.
    Raises ClientError on failure.
    """
    try:
        s3.upload_file(file_path, BUCKET, s3_key)
        logger.info("Uploaded %s → s3://%s/%s", file_path, BUCKET, s3_key)
        return s3_key
    except ClientError as exc:
        logger.error("S3 upload failed for %s: %s", s3_key, exc)
        raise


def upload_file_public(file_path: str, s3_key: str) -> str:
    """Upload a local file to S3 and return its public URL."""
    upload_file(file_path, s3_key)
    return get_public_url(s3_key)


# ─── Presigned URL ────────────────────────────────────────────────────────────


def generate_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Generate a time-limited presigned URL for an S3 object.

    S3 honours Range headers on presigned GETs for byte-range streaming.
    """
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
        return url
    except ClientError as exc:
        logger.error("Presigned URL generation failed for %s: %s", s3_key, exc)
        raise


# ─── Quota ────────────────────────────────────────────────────────────────────


def get_user_storage_usage(username: str) -> int:
    """Calculate total bytes stored under a user's S3 prefix."""
    total_bytes = 0
    prefixes = [f"uploads/{username}/", f"remixed/{username}/"]
    paginator = s3.get_paginator("list_objects_v2")

    for prefix in prefixes:
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                total_bytes += obj["Size"]

    return total_bytes


def check_quota(username: str, file_size: int, max_bytes: int = 5 * 1024**3) -> bool:
    """Return True if the upload is within the user's storage quota (default 5 GB)."""
    current_usage = get_user_storage_usage(username)
    within_quota = (current_usage + file_size) <= max_bytes
    if not within_quota:
        logger.warning(
            "User '%s' quota exceeded: current=%d, incoming=%d, max=%d",
            username, current_usage, file_size, max_bytes,
        )
    return within_quota
