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
    generate_presigned_upload_url,
    generate_presigned_url,
    get_public_url,
    check_quota,
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

        if body.asset_type == "reference":
            try:
                from shared.supabase_client import supabase as sb
                media_type = "image"
                if body.content_type and "video" in body.content_type:
                    media_type = "video"
                elif body.content_type and "audio" in body.content_type:
                    media_type = "audio"

                sb.table("generated_ads").insert({
                    "project_id": body.project_id,
                    "media_type": media_type,
                    "platform": "general",
                    "s3_media_key": s3_key,
                    "status": "completed",
                    "prompt_used": f"Uploaded reference: {body.filename}",
                    "metadata": {
                        "is_reference": True,
                        "filename": body.filename,
                        "s3_url": public_url
                    }
                }).execute()
                logger.info("[Files] Recorded reference asset %s in generated_ads", body.filename)
            except Exception as dberr:
                logger.error("[Files] Failed to record reference asset in DB: %s", dberr)

        return JSONResponse(content={
            "upload_url": upload_url,
            "s3_key": s3_key,
            "public_url": public_url,
            "filename": body.filename,
        })
    except Exception as e:
        logger.error("[Files] Failed to generate upload URL: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- Download URL -------------------------------------------------------------


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
    except Exception as e:
        logger.error("[Files] Failed to generate download URL: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
