"""
s3_client.py
────────────
Backward-compatibility shim. Use agent.s3_utils instead.
"""

import logging
import hashlib
import re
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urlparse

from botocore.exceptions import ClientError

from shared.clients import s3
from config import S3_REGION, S3_BUCKET_NAME
from shared.media_security import safe_filename

logger = logging.getLogger(__name__)

BUCKET = S3_BUCKET_NAME
REGION = S3_REGION

_SAFE_SCOPE_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _safe_scope(value: str, *, label: str) -> str:
    """Normalize a project/task scope without permitting prefix injection."""
    candidate = str(value or "").strip()
    if _SAFE_SCOPE_RE.fullmatch(candidate) and candidate not in {".", ".."}:
        return candidate
    if not candidate:
        raise ValueError(f"{label} is required")
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:32]
    return f"{label}-{digest}"


def opaque_user_prefix(user_id: str) -> str:
    """Derive a stable, non-PII S3 subject prefix from a verified user ID."""
    candidate = str(user_id or "").strip()
    if not candidate:
        raise ValueError("verified user_id is required")
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:32]
    return f"user-{digest}"


def is_private_key_for_user(s3_key: str, user_id: str) -> bool:
    """Return whether a canonical private key belongs to this principal."""
    key = normalize_s3_key(s3_key)
    if not key:
        return False
    subject = opaque_user_prefix(user_id)
    return any(
        key.startswith(f"private/{asset_prefix}/{subject}/")
        for asset_prefix in ("uploads", "remixed", "segmented")
    )



class S3MediaClient:
    """Legacy class wrapper — prefer using s3_utils functions directly."""

    def __init__(self, bucket_name=None, region=None):
        pass

    def upload_file(self, file_path, s3_key):
        return upload_file(file_path, s3_key)

    def upload_file_private(self, file_path, s3_key):
        return upload_file_private(file_path, s3_key)

    def get_public_url(self, s3_key):
        return get_public_url(s3_key)

    def upload_file_public(self, file_path, s3_key):
        return upload_file_public(file_path, s3_key)

    def generate_presigned_url(self, s3_key, expiry_seconds=3600, attachment_filename=None):
        return generate_presigned_url(s3_key, expiry_seconds, attachment_filename)

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
    """Construct a private, tenant-scoped S3 object key.

    asset_type: "upload" | "remixed" | "segmented"
    ``username`` is retained as a parameter name for source compatibility, but
    must be the immutable verified identity (for example Cognito ``sub``), not
    an email address or a client-provided username.
    """
    prefix_map = {"upload": "uploads", "remixed": "remixed", "segmented": "segmented"}
    prefix = prefix_map.get(asset_type)
    if prefix is None:
        raise ValueError(
            f"Invalid asset_type '{asset_type}'. Must be 'upload', 'remixed', or 'segmented'."
        )
    subject = opaque_user_prefix(username)
    project = _safe_scope(project_id, label="project")
    check = _safe_scope(check_id, label="check")
    name = safe_filename(filename)
    return f"private/{prefix}/{subject}/{project}/{check}/{name}"


def get_public_url(s3_key: str) -> str:
    """Return the public HTTPS URL for an S3 object (URL-encoded path)."""
    encoded_key = "/".join(quote(segment, safe="") for segment in s3_key.split("/"))
    return f"https://{BUCKET}.s3-{REGION}.amazonaws.com/{encoded_key}"


# --- Upload -------------------------------------------------------------------


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


def upload_file_private(file_path: str, s3_key: str) -> str:
    """Upload a private object and return only its canonical S3 key."""
    key = normalize_s3_key(s3_key)
    if not key or not key.startswith("private/"):
        raise ValueError("Invalid S3 object key")
    return upload_file(file_path, key)


def upload_file_public(file_path: str, s3_key: str) -> str:
    """Legacy compatibility helper.

    New source uploads, masks, voice samples, and remediation versions must use
    :func:`upload_file_private` and disclose only authorized presigned URLs.
    """
    logger.warning("upload_file_public is deprecated; use private storage and presigned reads")
    upload_file(file_path, s3_key)
    return get_public_url(s3_key)


# --- Delete -------------------------------------------------------------------


def delete_object(s3_key: str) -> None:
    """Delete exactly one validated S3 object key.

    This deliberately does not accept prefixes, globs, or URLs. Callers must
    authorize the asset record before invoking it.
    """
    normalized = normalize_s3_key(s3_key)
    if not normalized:
        raise ValueError("delete_object refused an invalid S3 key")
    try:
        s3.delete_object(Bucket=BUCKET, Key=normalized)
    except ClientError as exc:
        logger.error("S3 delete_object failed for %s: %s", normalized, exc)
        raise


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
        subject = opaque_user_prefix(owner_email)
        prefixes.extend(
            [
                f"private/uploads/{subject}/{project_id}/",
                f"private/remixed/{subject}/{project_id}/",
                f"private/segmented/{subject}/{project_id}/",
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


# --- Presigned URL ------------------------------------------------------------


def normalize_s3_key(value: str) -> str | None:
    """Return a canonical key, accepting only this bucket's legacy public URLs."""
    candidate = (value or "").strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        allowed_hosts = {
            f"{BUCKET}.s3.{REGION}.amazonaws.com",
            f"{BUCKET}.s3.amazonaws.com",
        }
        if parsed.scheme != "https" or parsed.netloc not in allowed_hosts:
            return None
        candidate = unquote(parsed.path.lstrip("/"))

    key = candidate.lstrip("/")
    if not key or ".." in PurePosixPath(key).parts:
        return None
    return key


def generate_presigned_url(
    s3_key: str,
    expiry_seconds: int = 3600,
    attachment_filename: str | None = None,
) -> str:
    """Generate a time-limited GET URL, optionally forcing an attachment download."""
    try:
        params = {"Bucket": BUCKET, "Key": s3_key}
        if attachment_filename:
            filename = PurePosixPath(attachment_filename).name.replace('"', "")
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        effective_expiry = (
            max(1, min(expiry_seconds, 900))
            if s3_key.startswith("private/")
            else expiry_seconds
        )
        url = s3.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=effective_expiry,
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
        effective_expiry = max(1, min(expiry_seconds, 900))
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=effective_expiry,
        )
        logger.info("Generated presigned PUT URL for %s (expires %ds)", s3_key, effective_expiry)
        return url
    except ClientError as exc:
        logger.error("Presigned PUT URL generation failed for %s: %s", s3_key, exc)
        raise


# --- Quota --------------------------------------------------------------------


def get_user_storage_usage(username: str) -> int:
    """Calculate total bytes stored under a user's S3 prefix."""
    total_bytes = 0
    subject = opaque_user_prefix(username)
    prefixes = [
        f"private/uploads/{subject}/",
        f"private/remixed/{subject}/",
        f"private/segmented/{subject}/",
    ]
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
