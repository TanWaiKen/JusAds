/**
 * File Service — S3 pre-signed URL upload/download operations.
 *
 * Architecture:
 *   1. Request a pre-signed URL from the backend
 *   2. Upload/download directly to/from S3
 *   3. Return the S3 key for reference in other API calls
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface UploadUrlResponse {
  upload_url: string;
  s3_key: string;
  public_url: string;
  filename: string;
}

interface DownloadUrlResponse {
  download_url: string;
  s3_key: string;
}

interface UploadOptions {
  filename: string;
  contentType: string;
  fileSize: number;
  username: string;
  projectId: string;
  assetType?: "upload" | "reference" | "generated";
}

/**
 * Uploads a file directly to S3 using a pre-signed URL.
 *
 * Flow:
 *   1. Requests a pre-signed PUT URL from the backend
 *   2. PUTs the file directly to S3
 *   3. Returns the S3 key and public URL
 */
export async function uploadFileToS3(
  file: File,
  options: UploadOptions
): Promise<UploadUrlResponse> {
  // Step 1: Get pre-signed upload URL from backend
  const urlRes = await fetch(`${API_BASE}/api/files/upload-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: options.filename,
      content_type: options.contentType,
      file_size: options.fileSize,
      username: options.username,
      project_id: options.projectId,
      asset_type: options.assetType ?? "upload",
    }),
  });

  if (!urlRes.ok) {
    const err = await urlRes.json().catch(() => ({ error: "Failed to get upload URL" }));
    throw new Error(err.error ?? `Upload URL request failed (${urlRes.status})`);
  }

  const data: UploadUrlResponse = await urlRes.json();

  // Step 2: Upload directly to S3
  const uploadRes = await fetch(data.upload_url, {
    method: "PUT",
    headers: { "Content-Type": options.contentType },
    body: file,
  });

  if (!uploadRes.ok) {
    throw new Error(`S3 upload failed (${uploadRes.status})`);
  }

  return data;
}

/**
 * Gets a temporary pre-signed download URL for an S3 object.
 * Use this to display or download files stored in S3.
 */
export async function getDownloadUrl(s3Key: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/files/download-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ s3_key: s3Key }),
  });

  if (!res.ok) {
    throw new Error(`Failed to get download URL (${res.status})`);
  }

  const data: DownloadUrlResponse = await res.json();
  return data.download_url;
}

/**
 * Convenience: upload a reference asset for the generation chatbot.
 * Returns the public URL that can be passed as a reference_url.
 */
export async function uploadReferenceAsset(
  file: File,
  projectId: string,
  _taskId: string,
  username: string
): Promise<{ publicUrl: string; s3Key: string }> {
  const result = await uploadFileToS3(file, {
    filename: file.name,
    contentType: file.type || "application/octet-stream",
    fileSize: file.size,
    username,
    projectId,
    assetType: "reference",
  });

  return {
    publicUrl: result.public_url,
    s3Key: result.s3_key,
  };
}
