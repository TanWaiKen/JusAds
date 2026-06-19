"""
s3_client.py
────────────
AWS S3 media storage client for the JusAds compliance pipeline.
Handles file uploads, presigned URL generation, and per-user storage quota enforcement.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, S3_BUCKET_NAME

logger = logging.getLogger(__name__)


def build_s3_key(
    asset_type: str,
    username: str,
    project_id: str,
    check_id: str,
    filename: str,
) -> str:
    """Construct an S3 object key following the project's path conventions.

    Args:
        asset_type: Either "upload" or "remixed".
        username: The owning user's identifier.
        project_id: UUID string of the project.
        check_id: Unique check identifier.
        filename: Original or generated filename.

    Returns:
        S3 key string in the format:
            uploads/{username}/{project_id}/{check_id}/{filename}
        or:
            remixed/{username}/{project_id}/{check_id}/{filename}

    Raises:
        ValueError: If asset_type is not "upload" or "remixed".
    """
    prefix_map = {
        "upload": "uploads",
        "remixed": "remixed",
        "segmented": "segmented",
    }
    prefix = prefix_map.get(asset_type)
    if prefix is None:
        raise ValueError(
            f"Invalid asset_type '{asset_type}'. Must be 'upload', 'remixed', or 'segmented'."
        )
    return f"{prefix}/{username}/{project_id}/{check_id}/{filename}"


class S3MediaClient:
    """Manages S3 uploads and presigned URL generation for the JusAds pipeline.

    Attributes:
        bucket_name: The S3 bucket used for media storage.
        region: AWS region where the bucket lives.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or S3_BUCKET_NAME
        self.region = region or AWS_REGION
        self._client = boto3.client("s3", region_name=self.region)

    def upload_file(self, file_path: str, s3_key: str) -> str:
        """Upload a local file to S3.

        Args:
            file_path: Absolute or relative path to the local file.
            s3_key: The destination key in S3.

        Returns:
            The S3 key of the uploaded object.

        Raises:
            ClientError: If the upload fails.
        """
        try:
            self._client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info("Uploaded %s → s3://%s/%s", file_path, self.bucket_name, s3_key)
            return s3_key
        except ClientError as exc:
            logger.error("S3 upload failed for %s: %s", s3_key, exc)
            raise

    def get_public_url(self, s3_key: str) -> str:
        """Return the public HTTPS URL for an S3 object.

        URL-encodes each path segment (handles spaces, @, and other special chars).

        Args:
            s3_key: The object key in S3.

        Returns:
            Public URL string with properly encoded path.
        """
        from urllib.parse import quote
        # Encode each segment of the key separately (preserve / as path separator)
        encoded_key = "/".join(quote(segment, safe="") for segment in s3_key.split("/"))
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{encoded_key}"

    def upload_file_public(self, file_path: str, s3_key: str) -> str:
        """Upload a local file to S3 and return its public URL.

        Args:
            file_path: Absolute or relative path to the local file.
            s3_key: The destination key in S3.

        Returns:
            The public URL of the uploaded object.

        Raises:
            ClientError: If the upload fails.
        """
        self.upload_file(file_path, s3_key)
        return self.get_public_url(s3_key)

    def generate_presigned_url(
        self,
        s3_key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Generate a time-limited presigned URL for an S3 object.

        The URL supports HTTP Range requests natively — S3 honours
        Range headers on presigned GETs, enabling byte-range streaming
        for video/audio playback without additional configuration.

        Args:
            s3_key: The object key in S3.
            expiry_seconds: URL validity duration in seconds (default 1 hour).

        Returns:
            A presigned HTTPS URL string.

        Raises:
            ClientError: If URL generation fails.
        """
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiry_seconds,
            )
            return url
        except ClientError as exc:
            logger.error("Presigned URL generation failed for %s: %s", s3_key, exc)
            raise

    def get_user_storage_usage(self, username: str) -> int:
        """Calculate total bytes stored under a user's S3 prefix.

        Iterates over both `uploads/{username}/` and `remixed/{username}/`
        prefixes, summing object sizes.

        Args:
            username: The user identifier.

        Returns:
            Total bytes stored for the user.
        """
        total_bytes = 0
        prefixes = [f"uploads/{username}/", f"remixed/{username}/"]
        paginator = self._client.get_paginator("list_objects_v2")

        for prefix in prefixes:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    total_bytes += obj["Size"]

        return total_bytes

    def check_quota(
        self,
        username: str,
        file_size: int,
        max_bytes: int = 5 * 1024**3,
    ) -> bool:
        """Check whether an upload would exceed the user's storage quota.

        Args:
            username: The user identifier.
            file_size: Size of the file to be uploaded, in bytes.
            max_bytes: Maximum allowed storage per user (default 5 GB).

        Returns:
            True if the upload is within quota, False if it would exceed it.
        """
        current_usage = self.get_user_storage_usage(username)
        within_quota = (current_usage + file_size) <= max_bytes
        if not within_quota:
            logger.warning(
                "User '%s' quota exceeded: current=%d, incoming=%d, max=%d",
                username,
                current_usage,
                file_size,
                max_bytes,
            )
        return within_quota
