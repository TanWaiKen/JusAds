/**
 * ReferenceUpload — Drag-and-drop image upload with presigned URL flow.
 *
 * Allows users to upload reference images for visual style guidance during
 * ad generation. Uses the existing presigned URL upload flow from fileService.
 *
 * Requirements: 4.1, 4.2, 4.3
 */

import { useCallback, useRef, useState } from "react";
import { Upload, X, RefreshCw, AlertCircle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface ReferenceUploadProps {
  referenceUrls: string[];
  onAddUrl: (url: string) => void;
  onRemoveUrl: (index: number) => void;
}

interface UploadItem {
  id: string;
  file: File;
  status: "uploading" | "failed";
  previewUrl: string;
  errorMessage?: string;
}

/**
 * Uploads a single file to S3 using the presigned URL flow.
 *
 * 1. Requests a presigned PUT URL from the backend
 * 2. Uploads the file directly to S3
 * 3. Returns the public URL for the uploaded asset
 */
async function uploadToS3(file: File): Promise<string> {
  const res = await fetch(`${API_BASE}/api/files/upload-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type || "image/png",
      file_size: file.size,
      username: "easy-mode",
      project_id: "reference",
      asset_type: "reference",
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Failed to get upload URL" }));
    throw new Error(err.error ?? `Upload URL request failed (${res.status})`);
  }

  const data = await res.json();

  const uploadRes = await fetch(data.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "image/png" },
    body: file,
  });

  if (!uploadRes.ok) {
    throw new Error(`S3 upload failed (${uploadRes.status})`);
  }

  return data.public_url;
}

export function ReferenceUpload({
  referenceUrls,
  onAddUrl,
  onRemoveUrl,
}: ReferenceUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [pendingUploads, setPendingUploads] = useState<UploadItem[]>([]);

  const processFiles = useCallback(
    async (files: File[]) => {
      const imageFiles = files.filter((f) => f.type.startsWith("image/"));
      if (imageFiles.length === 0) return;

      const newItems: UploadItem[] = imageFiles.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        status: "uploading" as const,
        previewUrl: URL.createObjectURL(file),
      }));

      setPendingUploads((prev) => [...prev, ...newItems]);

      for (const item of newItems) {
        try {
          const publicUrl = await uploadToS3(item.file);
          onAddUrl(publicUrl);
          setPendingUploads((prev) => prev.filter((p) => p.id !== item.id));
          URL.revokeObjectURL(item.previewUrl);
        } catch (err) {
          const message =
            err instanceof Error ? err.message : "Upload failed";
          setPendingUploads((prev) =>
            prev.map((p) =>
              p.id === item.id
                ? { ...p, status: "failed" as const, errorMessage: message }
                : p
            )
          );
        }
      }
    },
    [onAddUrl]
  );

  const handleRetry = useCallback(
    async (item: UploadItem) => {
      setPendingUploads((prev) =>
        prev.map((p) =>
          p.id === item.id ? { ...p, status: "uploading" as const, errorMessage: undefined } : p
        )
      );

      try {
        const publicUrl = await uploadToS3(item.file);
        onAddUrl(publicUrl);
        setPendingUploads((prev) => prev.filter((p) => p.id !== item.id));
        URL.revokeObjectURL(item.previewUrl);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Upload failed";
        setPendingUploads((prev) =>
          prev.map((p) =>
            p.id === item.id
              ? { ...p, status: "failed" as const, errorMessage: message }
              : p
          )
        );
      }
    },
    [onAddUrl]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      processFiles(files);
    },
    [processFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      processFiles(files);
      // Reset input so re-selecting the same file triggers change
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [processFiles]
  );

  const handleDismissFailed = useCallback((id: string) => {
    setPendingUploads((prev) => {
      const item = prev.find((p) => p.id === id);
      if (item) URL.revokeObjectURL(item.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  }, []);

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-foreground">
        Reference Images
      </label>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        className={`
          relative flex flex-col items-center justify-center gap-2
          rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer
          ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
          }
        `}
        onClick={handleBrowseClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleBrowseClick();
          }
        }}
        aria-label="Upload reference images. Drag and drop or click to browse."
      >
        <Upload className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm text-muted-foreground text-center">
          Drag & drop images here, or{" "}
          <span className="text-primary font-medium underline">browse</span>
        </p>
        <p className="text-xs text-muted-foreground/60">
          Accepts image files only
        </p>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleFileChange}
        aria-hidden="true"
      />

      {/* Thumbnail grid */}
      {(referenceUrls.length > 0 || pendingUploads.length > 0) && (
        <div className="grid grid-cols-4 gap-2">
          {/* Successfully uploaded thumbnails */}
          {referenceUrls.map((url, index) => (
            <div
              key={`uploaded-${index}`}
              className="relative group aspect-square rounded-md overflow-hidden border border-border"
            >
              <img
                src={url}
                alt={`Reference ${index + 1}`}
                className="h-full w-full object-cover"
              />
              <button
                type="button"
                onClick={() => onRemoveUrl(index)}
                className="
                  absolute top-1 right-1 rounded-full bg-destructive p-0.5
                  opacity-0 group-hover:opacity-100 transition-opacity
                  focus:opacity-100
                "
                aria-label={`Remove reference image ${index + 1}`}
              >
                <X className="h-3 w-3 text-destructive-foreground" />
              </button>
            </div>
          ))}

          {/* Pending uploads (uploading or failed) */}
          {pendingUploads.map((item) => (
            <div
              key={item.id}
              className="relative aspect-square rounded-md overflow-hidden border border-border"
            >
              <img
                src={item.previewUrl}
                alt="Uploading reference"
                className={`h-full w-full object-cover ${
                  item.status === "uploading" ? "opacity-50" : "opacity-40"
                }`}
              />

              {item.status === "uploading" && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <RefreshCw className="h-4 w-4 text-primary animate-spin" />
                </div>
              )}

              {item.status === "failed" && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/40 p-1">
                  <AlertCircle className="h-4 w-4 text-destructive" />
                  <p className="text-[10px] text-white text-center leading-tight">
                    Upload failed
                  </p>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => handleRetry(item)}
                      className="text-[10px] text-primary underline hover:text-primary/80"
                      aria-label="Retry upload"
                    >
                      Retry
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDismissFailed(item.id)}
                      className="text-[10px] text-muted-foreground underline hover:text-muted-foreground/80"
                      aria-label="Dismiss failed upload"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
