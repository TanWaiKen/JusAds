import { useState, useRef, type ChangeEvent } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { UploadParams } from "@/types/compliance";

interface UploadFormProps {
  onSubmit: (params: UploadParams) => void;
  isSubmitting: boolean;
}

const ACCEPTED_FILE_TYPES = "video/*,image/*,audio/*";
const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const MARKET_OPTIONS = ["malaysia", "singapore", "indonesia", "thailand"];
const ETHNICITY_OPTIONS = ["malay", "chinese", "indian", "mixed"];
const AGE_GROUP_OPTIONS = ["all_ages", "children", "teens", "adults", "seniors"];

function getMediaTypeIcon(mimeType: string): string {
  if (mimeType.startsWith("video/")) return "videocam";
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("audio/")) return "audio_file";
  return "description";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatLabel(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function UploadForm({ onSubmit, isSubmitting }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [market, setMarket] = useState("malaysia");
  const [ethnicity, setEthnicity] = useState("malay");
  const [ageGroup, setAgeGroup] = useState("all_ages");
  const [fileSizeWarning, setFileSizeWarning] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasContent = file !== null || text.trim().length > 0;
  const isDisabled = !hasContent || isSubmitting;

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0] ?? null;
    setFileSizeWarning(null);

    if (selectedFile && selectedFile.size > MAX_FILE_SIZE_BYTES) {
      setFileSizeWarning(
        `File size (${formatFileSize(selectedFile.size)}) exceeds the ${MAX_FILE_SIZE_MB}MB limit.`
      );
    }

    setFile(selectedFile);
  }

  function handleRemoveFile() {
    setFile(null);
    setFileSizeWarning(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleSubmit() {
    if (isDisabled) return;

    onSubmit({
      file: file ?? undefined,
      text: text.trim() || undefined,
      market,
      ethnicity,
      ageGroup,
    });
  }

  return (
    <div className="bg-surface-panel rounded-xl p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
      <h3 className="font-label-ui text-label-ui font-bold text-text-primary mb-4">
        Upload Asset for Compliance Check
      </h3>

      {/* File Upload Area */}
      <div className="mb-4">
        <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-2 block">
          File Upload
        </label>
        <div
          className="border border-dashed border-outline-variant rounded-xl p-4 text-center cursor-pointer hover:bg-surface-container transition-colors"
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={handleFileChange}
            className="hidden"
          />
          {!file ? (
            <div className="flex flex-col items-center gap-2 py-2">
              <span className="material-symbols-outlined text-text-muted text-[32px]">
                upload_file
              </span>
              <p className="text-body-md font-body-md text-text-muted">
                Click to upload video, image, or audio
              </p>
              <p className="text-code-xs font-code-xs text-text-muted">
                Supports video/*, image/*, audio/* (max {MAX_FILE_SIZE_MB}MB)
              </p>
            </div>
          ) : (
            <div
              className="flex items-center gap-3 text-left"
              onClick={(e) => e.stopPropagation()}
            >
              <span
                className="material-symbols-outlined text-aurora-purple text-[24px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                {getMediaTypeIcon(file.type)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-label-ui text-label-ui text-text-primary truncate">
                  {file.name}
                </p>
                <p className="text-code-xs font-code-xs text-text-muted">
                  {formatFileSize(file.size)}
                </p>
              </div>
              <button
                type="button"
                onClick={handleRemoveFile}
                className="text-text-muted hover:text-error transition-colors p-1"
                aria-label="Remove file"
              >
                <span className="material-symbols-outlined text-[18px]">
                  close
                </span>
              </button>
            </div>
          )}
        </div>

        {fileSizeWarning && (
          <div className="mt-2 flex items-center gap-2 text-error text-code-xs font-code-xs">
            <span className="material-symbols-outlined text-[14px]">
              warning
            </span>
            {fileSizeWarning}
          </div>
        )}
      </div>

      {/* Text Input */}
      <div className="mb-4">
        <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-2 block">
          Or enter text ad copy
        </label>
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your ad copy text here..."
          className="resize-none"
          rows={3}
        />
      </div>

      {/* Parameter Dropdowns */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        {/* Market */}
        <div>
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-1.5 block">
            Market
          </label>
          <Select value={market} onValueChange={(v) => v && setMarket(v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MARKET_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {formatLabel(option)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Ethnicity */}
        <div>
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-1.5 block">
            Ethnicity
          </label>
          <Select value={ethnicity} onValueChange={(v) => v && setEthnicity(v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ETHNICITY_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {formatLabel(option)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Age Group */}
        <div>
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-1.5 block">
            Age Group
          </label>
          <Select value={ageGroup} onValueChange={(v) => v && setAgeGroup(v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AGE_GROUP_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {formatLabel(option)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Submit Button */}
      <Button
        onClick={handleSubmit}
        disabled={isDisabled}
        className="w-full rounded-lg font-label-ui [font-size:14px] py-3 h-auto"
      >
        {isSubmitting ? (
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] animate-spin">
              sync
            </span>
            Checking compliance...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">
              verified_user
            </span>
            Run Compliance Check
          </span>
        )}
      </Button>
    </div>
  );
}
