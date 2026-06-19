"""
validators.py
─────────────
File size, user quota, and storage threshold validation for the JusAds pipeline.

Provides validation functions that raise HTTPException(400) on constraint violations:
- validate_file_size: rejects uploads exceeding 100 MB
- validate_user_quota: rejects uploads exceeding the 5 GB per-user S3 quota
- check_supabase_storage_warning: logs a warning when Supabase DB usage
  exceeds 400 MB (80% of the 500 MB free-tier limit)

Requirements: 6.5, 6.6, 6.7
"""

import logging

from fastapi import HTTPException

from agent.s3_client import S3MediaClient

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES: int = 104_857_600  # 100 MB exactly
MAX_USER_QUOTA_BYTES: int = 5 * 1024**3  # 5 GB = 5,368,709,120 bytes
SUPABASE_WARNING_THRESHOLD_BYTES: int = 400 * 1024 * 1024  # 400 MB


# ── Validation Functions ──────────────────────────────────────────────────────


def validate_file_size(file_size_bytes: int) -> None:
    """Validate that the uploaded file does not exceed the 100 MB limit.

    Args:
        file_size_bytes: Size of the file in bytes.

    Raises:
        HTTPException: 400 status if the file exceeds 104,857,600 bytes.
    """
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File size ({file_size_bytes:,} bytes) exceeds the maximum "
                f"allowed size of 100 MB ({MAX_FILE_SIZE_BYTES:,} bytes)."
            ),
        )


def validate_user_quota(
    username: str,
    file_size: int,
    s3_client: S3MediaClient,
    max_bytes: int = MAX_USER_QUOTA_BYTES,
) -> None:
    """Validate that the upload would not exceed the user's S3 storage quota.

    Checks the user's current S3 usage and rejects the upload if adding the
    new file would exceed the per-user maximum (default 5 GB).

    Args:
        username: The user identifier.
        file_size: Size of the file to be uploaded, in bytes.
        s3_client: An S3MediaClient instance for querying current usage.
        max_bytes: Maximum allowed storage per user in bytes (default 5 GB).

    Raises:
        HTTPException: 400 status if the upload would exceed the quota.
    """
    current_usage = s3_client.get_user_storage_usage(username)
    if (current_usage + file_size) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Storage quota exceeded for user '{username}'. "
                f"Current usage: {current_usage:,} bytes, "
                f"incoming file: {file_size:,} bytes, "
                f"maximum allowed: {max_bytes:,} bytes (5 GB). "
                f"Please delete existing files to free up space."
            ),
        )


def check_supabase_storage_warning(db_usage_bytes: int) -> None:
    """Log a warning if Supabase database usage exceeds 80% of the free tier.

    This is a best-effort check. It logs a warning when the database usage
    exceeds 400 MB (80% of the 500 MB free-tier limit) to alert operators
    for capacity planning.

    Args:
        db_usage_bytes: Current database usage in bytes.
    """
    if db_usage_bytes > SUPABASE_WARNING_THRESHOLD_BYTES:
        logger.warning(
            "Supabase storage threshold reached: current usage %d bytes "
            "(%.1f MB) exceeds 80%% of the 500 MB free-tier limit. "
            "Consider upgrading or cleaning up old records.",
            db_usage_bytes,
            db_usage_bytes / (1024 * 1024),
        )
