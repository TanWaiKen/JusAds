"""
s3_client.py
────────────
Backward-compatibility shim. Use agent.s3_utils instead.
"""

import logging
from urllib.parse import quote

from botocore.exceptions import ClientError

from shared.clients import s3
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


# ─── Delete ───────────────────────────────────────────────────────────────────


def delete_prefix(prefix: str) -> int:
    """Delete every S3 object under a key prefix. Returns the count deleted.

    S3 has no real folders: objects are listed by ``prefix`` (paginated, 1000 at
    a time) and removed in batched ``delete_objects`` calls (also capped at 1000
    keys per call). This is irreversible unless the bucket has versioning.

    Guards against an empty/blank prefix so a bad caller can never target the
    whole bucket. Any per-page failure is logged and re-raised so the caller can
    decide how to degrade — no object is silently left in an unknown state.

    Args:
        prefix: The S3 key prefix to purge (e.g. ``generated_ads/{project_id}/``).

    Returns:
        The number of objects deleted (0 when the prefix is empty).

    Raises:
        ValueError: If ``prefix`` is blank (refuses a whole-bucket wipe).
        ClientError: If an S3 list/delete call fails.
    """
    normalized = (prefix or "").strip()
    if not normalized:
        raise ValueError("delete_prefix refused: empty prefix would target the whole bucket")

    deleted = 0
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET, Prefix=normalized):
            contents = page.get("Contents") or []
            if not contents:
                continue
            # delete_objects accepts up to 1000 keys per request.
            for start in range(0, len(contents), 1000):
                batch = contents[start : start + 1000]
                objects = [{"Key": obj["Key"]} for obj in batch]
                s3.delete_objects(Bucket=BUCKET, Delete={"Objects": objects, "Quiet": True})
                deleted += len(objects)
        logger.info("Deleted %d object(s) under s3://%s/%s", deleted, BUCKET, normalized)
        return deleted
    except ClientError as exc:
        logger.error("S3 delete_prefix failed for %s: %s", normalized, exc)
        raise


def delete_project_media(project_id: str, owner_email: str | None = None) -> int:
    """Delete all S3 media belonging to a project. Returns total objects removed.

    Purges the project-scoped prefixes:

    * ``generated_ads/{project_id}/`` — generated ads and uploaded references
      (this prefix is keyed solely by project, so no owner is needed).
    * ``uploads/{owner_email}/{project_id}/`` — compliance-check source media.
    * ``remixed/{owner_email}/{project_id}/`` — remediated outputs.
    * ``segmented/{owner_email}/{project_id}/`` — segmented / mask images.

    The owner-scoped prefixes are only purged when ``owner_email`` is provided
    (the compliance keys embed the owner). Each prefix is deleted independently
    so a failure on one is logged and does not prevent the others from being
    attempted; the function never raises (best-effort cleanup on project delete).

    Args:
        project_id: The project whose media should be removed.
        owner_email: The project owner's email (username in compliance keys).

    Returns:
        The total number of S3 objects deleted across all prefixes.
    """
    if not project_id:
        logger.warning("delete_project_media: no project_id; skipping S3 cleanup")
        return 0

    prefixes = [f"generated_ads/{project_id}/"]
    if owner_email:
        prefixes.extend(
            [
                f"uploads/{owner_email}/{project_id}/",
                f"remixed/{owner_email}/{project_id}/",
                f"segmented/{owner_email}/{project_id}/",
            ]
        )

    total = 0
    for prefix in prefixes:
        try:
            total += delete_prefix(prefix)
        except Exception as exc:  # noqa: BLE001 - best-effort; keep purging siblings
            logger.error("delete_project_media: failed to purge %s: %s", prefix, exc)
    logger.info("delete_project_media: removed %d S3 object(s) for project %s", total, project_id)
    return total


# ─── Presigned URL ────────────────────────────────────────────────────────────


def generate_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Generate a time-limited presigned GET URL for an S3 object.

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


def generate_presigned_upload_url(
    s3_key: str,
    content_type: str = "application/octet-stream",
    expiry_seconds: int = 3600,
) -> str:
    """Generate a time-limited presigned PUT URL for direct frontend-to-S3 upload.

    The frontend uses this URL with a PUT request to upload the file directly
    without routing through the backend server.
    """
    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=expiry_seconds,
        )
        logger.info("Generated presigned PUT URL for %s (expires %ds)", s3_key, expiry_seconds)
        return url
    except ClientError as exc:
        logger.error("Presigned PUT URL generation failed for %s: %s", s3_key, exc)
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
