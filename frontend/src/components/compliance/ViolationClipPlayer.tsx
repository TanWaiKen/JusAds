import { API_BASE } from "@/services/complianceApi";

interface ViolationClipPlayerProps {
  clipUrl: string | null;
  start: number;
  end: number;
}

/**
 * Formats seconds into "M:SS" display (e.g. 65 → "1:05")
 */
function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function ViolationClipPlayer({
  clipUrl,
  start,
  end,
}: ViolationClipPlayerProps) {
  return (
    <div className="rounded-lg overflow-hidden">
      {clipUrl ? (
        <video
          className="w-full aspect-video bg-black"
          src={`${API_BASE}${clipUrl}`}
          controls
          playsInline
        />
      ) : (
        <div className="w-full aspect-video bg-surface-container flex flex-col items-center justify-center gap-2">
          <span
            className="material-symbols-outlined text-[32px] text-text-muted"
            style={{ fontVariationSettings: "'FILL' 0" }}
          >
            videocam_off
          </span>
          <span className="text-label-ui text-text-muted">
            Clip unavailable
          </span>
        </div>
      )}

      {/* Timestamp range */}
      <div className="px-2 py-1.5">
        <span className="text-code-xs font-code-xs text-text-muted">
          {formatTimestamp(start)} – {formatTimestamp(end)}
        </span>
      </div>
    </div>
  );
}
