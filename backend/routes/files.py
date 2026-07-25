"""
routes/files.py
───────────────
S3 pre-signed URL endpoints for direct frontend-to-S3 uploads and downloads.

Architecture:
  1. Frontend requests a pre-signed URL from this endpoint.
  2. Frontend uploads/downloads directly to/from S3 using that URL.
  3. Frontend notifies backend with the S3 key and metadata if needed.

This avoids routing large files through the API server.
"""

import uuid
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.s3_client import (
    check_quota,
    generate_presigned_upload_url,
    generate_presigned_url,
    get_public_url,
    normalize_s3_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


# --- Request/Response Models --------------------------------------------------


class UploadUrlRequest(BaseModel):
    """Request body for generating a pre-signed upload URL."""
    filename: str
    content_type: str = "application/octet-stream"
    file_size: int = 0
    username: str
    project_id: str
    asset_type: str = "upload"  # "upload" | "reference" | "generated"


class DownloadUrlRequest(BaseModel):
    """Request body for generating a pre-signed download URL."""
    s3_key: str


class CompleteUploadRequest(BaseModel):
    """Confirm a completed direct upload so a reference becomes a library asset."""
    s3_key: str
    filename: str
    content_type: str = "application/octet-stream"
    project_id: str
    asset_type: str = "upload"


class AssetDownloadRequest(BaseModel):
    """Request an asset download after validating the requesting project owner."""
    asset_id: str
    user_email: str


# --- Upload URL ---------------------------------------------------------------


@router.post("/upload-url")
async def get_upload_url(body: UploadUrlRequest) -> JSONResponse:
    """Generate a pre-signed PUT URL for direct-to-S3 upload.

    Flow:
      1. Frontend calls this with filename, content_type, size, username, project_id.
      2. Backend checks quota, generates a unique S3 key, returns presigned PUT URL.
      3. Frontend uploads directly to S3 using the URL.
      4. Frontend uses the returned s3_key/public_url as needed.
    """
    # Quota check (5 GB default)
    if body.file_size > 0:
        within_quota = check_quota(body.username, body.file_size)
        if not within_quota:
            return JSONResponse(
                status_code=413,
                content={"error": "Storage quota exceeded (5 GB limit)"},
            )

    # File size limit: 100 MB per file
    if body.file_size > 100 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={"error": "File too large. Maximum upload size is 100 MB."},
        )

    # Build S3 key
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = body.filename.replace(" ", "_")

    prefix_map = {
        "upload": "uploads",
        "reference": "generated_ads",
        "generated": "generated_ads",
    }
    prefix = prefix_map.get(body.asset_type, "uploads")
    s3_key = f"{prefix}/{body.username}/{body.project_id}/{unique_id}_{safe_filename}"

    try:
        upload_url = generate_presigned_upload_url(s3_key, body.content_type)
        public_url = get_public_url(s3_key)

        logger.info(
            "[Files] Generated upload URL for %s (%s, %d bytes)",
            safe_filename, body.content_type, body.file_size,
        )

        return JSONResponse(content={
            "upload_url": upload_url,
            "s3_key": s3_key,
            "public_url": public_url,
            "filename": body.filename,
        })
    except Exception:
        logger.exception("[Files] Failed to generate upload URL")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to prepare the upload. Please try again."},
        )


@router.post("/upload-complete")
async def complete_upload(body: CompleteUploadRequest) -> JSONResponse:
    """Record a completed direct reference upload in the user's asset library."""
    if body.asset_type != "reference":
        return JSONResponse(content={"recorded": False})

    s3_key = normalize_s3_key(body.s3_key)
    if not s3_key:
        return JSONResponse(status_code=400, content={"error": "Invalid S3 object key"})

    try:
        from shared.supabase_client import supabase as sb

        existing = (
            sb.table("generated_ads")
            .select("id")
            .eq("project_id", body.project_id)
            .eq("s3_media_key", s3_key)
            .limit(1)
            .execute()
        )
        if existing.data:
            return JSONResponse(content={"recorded": True, "asset_id": str(existing.data[0]["id"])})

        media_type = "image"
        if "video" in body.content_type:
            media_type = "video"
        elif "audio" in body.content_type:
            media_type = "audio"
        elif "text" in body.content_type:
            media_type = "text"

        response = sb.table("generated_ads").insert({
            "project_id": body.project_id,
            "media_type": media_type,
            "platform": "general",
            "s3_media_key": s3_key,
            "status": "completed",
            "asset_role": "reference",
            "prompt_used": f"Uploaded reference: {body.filename}",
            "metadata": {
                "is_reference": True,
                "filename": body.filename,
                "s3_url": get_public_url(s3_key),
            },
        }).execute()
        row = (response.data or [{}])[0]
        logger.info("[Files] Recorded completed reference upload %s", body.filename)
        return JSONResponse(content={"recorded": True, "asset_id": str(row.get("id", ""))})
    except Exception:
        logger.exception("[Files] Failed to record completed reference upload")
        return JSONResponse(status_code=500, content={"error": "Upload succeeded but could not be saved to your asset library."})


@router.post("/asset-download-url")
async def get_asset_download_url(body: AssetDownloadRequest) -> JSONResponse:
    """Return a download URL for an asset owned by the requesting user's project."""
    asset_id = body.asset_id.strip()
    user_email = body.user_email.strip().lower()
    if not asset_id or not user_email:
        return JSONResponse(status_code=400, content={"error": "asset_id and user_email are required"})

    try:
        from shared.supabase_client import supabase as sb

        response = (
            sb.table("generated_ads")
            .select("id, project_id, media_type, s3_media_key, metadata, projects!inner(owner_email)")
            .eq("id", asset_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Asset not found"})

        asset = rows[0]
        project = asset.get("projects") or {}
        if project.get("owner_email", "").strip().lower() != user_email:
            return JSONResponse(status_code=403, content={"error": "Access denied"})

        s3_key = normalize_s3_key(str(asset.get("s3_media_key") or ""))
        if not s3_key:
            return JSONResponse(status_code=409, content={"error": "This asset has no downloadable file"})

        metadata = asset.get("metadata") or {}
        filename = str(metadata.get("filename") or s3_key.rsplit("/", 1)[-1])
        download_url = generate_presigned_url(
            s3_key,
            expiry_seconds=3600,
            attachment_filename=filename,
        )
        logger.info("[Files] Generated asset download URL for %s", asset_id)
        return JSONResponse(content={"download_url": download_url, "filename": filename})
    except Exception:
        logger.exception("[Files] Failed to generate owned asset download URL")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to prepare the download. Please try again."},
        )


@router.post("/download-url")
async def get_download_url(body: DownloadUrlRequest) -> JSONResponse:
    """Generate a pre-signed GET URL for downloading a file from S3.

    Returns a temporary URL (expires in 1 hour) for the frontend to
    download or display the file directly from S3.
    """
    if not body.s3_key:
        return JSONResponse(status_code=400, content={"error": "s3_key is required"})

    try:
        download_url = generate_presigned_url(body.s3_key, expiry_seconds=3600)
        logger.info("[Files] Generated download URL for %s", body.s3_key)
        return JSONResponse(content={
            "download_url": download_url,
            "s3_key": body.s3_key,
        })
    except Exception:
        logger.exception("[Files] Failed to generate download URL")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to prepare the download. Please try again."},
        )
