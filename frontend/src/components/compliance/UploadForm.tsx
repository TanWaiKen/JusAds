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
import { FileText, ImageIcon, Music, Video } from "lucide-react";
import type { UploadParams } from "@/types/compliance";

interface UploadFormProps {
  onSubmit: (params: UploadParams) => void;
  isSubmitting: boolean;
}

type MediaMode = "text" | "image" | "audio" | "video";

const ACCEPT_MAP: Record<MediaMode, string> = {
  text: "",
  image: "image/jpeg, image/png, image/jpg",
  audio: "audio/*",
  video: "video/*",
};

const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const MARKET_OPTIONS = ["malaysia", "singapore", "indonesia", "thailand"];
const ETHNICITY_OPTIONS = ["malay", "chinese", "indian", "mixed"];
const AGE_GROUP_OPTIONS = ["all_ages", "children", "teens", "adults", "seniors"];
const PLATFORM_OPTIONS = ["general", "tiktok", "youtube", "instagram", "meta", "x"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatLabel(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const MODE_CONFIG: { mode: MediaMode; label: string; icon: typeof FileText }[] = [
  { mode: "image", label: "Image", icon: ImageIcon },
  { mode: "video", label: "Video", icon: Video },
  { mode: "audio", label: "Audio", icon: Music },
  { mode: "text", label: "Text", icon: FileText },
];

export function UploadForm({ onSubmit, isSubmitting }: UploadFormProps) {
  const [mediaMode, setMediaMode] = useState<MediaMode>("image");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [market, setMarket] = useState("malaysia");
  const [ethnicity, setEthnicity] = useState("malay");
  const [ageGroup, setAgeGroup] = useState("all_ages");
  const [platform, setPlatform] = useState("general");
  const [fileSizeWarning, setFileSizeWarning] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasContent = mediaMode === "text" ? text.trim().length > 0 : file !== null;
  const isDisabled = !hasContent || isSubmitting;

  function handleModeChange(mode: MediaMode) {
    setMediaMode(mode);
    setFile(null);
    setText("");
    setFileSizeWarning(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

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
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleSubmit() {
    if (isDisabled) return;

    onSubmit({
      file: file ?? undefined,
      text: mediaMode === "text" ? text.trim() : undefined,
      market,
      ethnicity,
      ageGroup,
      platform,
    });
  }

  return (
    <div className="bg-surface-panel rounded-xl p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
      <h3 className="font-label-ui text-label-ui font-semibold text-text-primary mb-4">
        Upload Asset for Compliance Check
      </h3>

      {/* Media Type Selector */}
      <div className="mb-5">
        <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-2 block">
          Media Type
        </label>
        <div className="grid grid-cols-4 gap-2">
          {MODE_CONFIG.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => handleModeChange(mode)}
              className={`flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 transition-all ${
                mediaMode === mode
                  ? "border-accent-blue bg-accent-blue/5 text-accent-blue"
                  : "border-outline-variant text-text-muted hover:border-text-body hover:text-text-body"
              }`}
            >
              <Icon size={20} />
              <span className="text-[11px] font-semibold">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* File Upload Area — for image/video/audio */}
      {mediaMode !== "text" && (
        <div className="mb-4">
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-2 block">
            Upload {mediaMode} file
          </label>
          <div
            className="border border-dashed border-outline-variant rounded-xl p-4 text-center cursor-pointer hover:bg-surface-container transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_MAP[mediaMode]}
              onChange={handleFileChange}
              className="hidden"
            />
            {!file ? (
              <div className="flex flex-col items-center gap-2 py-2">
                <span className="material-symbols-outlined text-text-muted text-[32px]">
                  upload_file
                </span>
                <p className="text-body-md font-body-md text-text-muted">
                  Click to upload {mediaMode} file
                </p>
                <p className="text-code-xs font-code-xs text-text-muted">
                  Accepts {ACCEPT_MAP[mediaMode]} (max {MAX_FILE_SIZE_MB}MB)
                </p>
              </div>
            ) : (
              <div
                className="flex items-center gap-3 text-left"
                onClick={(e) => e.stopPropagation()}
              >
                <span className="material-symbols-outlined text-aurora-purple text-[24px]">
                  {mediaMode === "video" ? "videocam" : mediaMode === "audio" ? "audio_file" : "image"}
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
                  <span className="material-symbols-outlined text-[18px]">close</span>
                </button>
              </div>
            )}
          </div>

          {fileSizeWarning && (
            <div className="mt-2 flex items-center gap-2 text-error text-code-xs font-code-xs">
              <span className="material-symbols-outlined text-[14px]">warning</span>
              {fileSizeWarning}
            </div>
          )}
        </div>
      )}

      {/* Text Input — only for text mode */}
      {mediaMode === "text" && (
        <div className="mb-4">
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-2 block">
            Ad Copy Text
          </label>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your ad copy text here..."
            className="resize-none"
            rows={5}
          />
        </div>
      )}

      {/* Parameter Dropdowns */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
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

        <div>
          <label className="text-[12px] font-label-ui text-text-muted uppercase tracking-wider mb-1.5 block">
            Platform
          </label>
          <Select value={platform} onValueChange={(v) => v && setPlatform(v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PLATFORM_OPTIONS.map((option) => (
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
            <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
            Checking compliance...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">verified_user</span>
            Run Compliance Check
          </span>
        )}
      </Button>
    </div>
  );
}
