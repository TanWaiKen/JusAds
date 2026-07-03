/**
 * Agentic Ad Studio — Output Gallery (Req 11.1–11.4)
 *
 * Renders generated outputs grouped by media-type section (Req 11.1), each
 * output shown as a card with a per-output compliance badge — compliant,
 * non-compliant, or pending (Req 11.2). A pending indicator persists on an
 * output until the user explicitly clears it (Req 11.3). If a badge cannot
 * render, the ad is still shown together with a "status unavailable" fallback
 * rather than being hidden (Req 11.4).
 */

import React, { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  X,
  FileText,
  ImageIcon,
  Play,
  Pause,
  Volume2,
  Rocket,
  Loader2,
  ChevronDown,
  Info,
  Lightbulb,
  Send,
} from "lucide-react";
import {
  groupAdsByMediaType,
  MEDIA_TYPES,
  publishAd,
  distributeAd,
  type GeneratedAdView,
  type MediaType,
  type ComplianceStatus,
  type ComplianceReasons,
} from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

interface OutputGalleryProps {
  ads: GeneratedAdView[];
  isSidebar?: boolean;
  projectId?: string;
  taskId?: string;
}

// ─── Custom Audio Player ─────────────────────────────────────────────────────

interface AudioPlayerProps {
  src: string;
}

function AudioPlayer({ src }: AudioPlayerProps): React.ReactElement {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    const audio = audioRef.current;
    if (!audio) return;
    setCurrentTime(audio.currentTime);
    setProgress(audio.duration ? (audio.currentTime / audio.duration) * 100 : 0);
  };

  const handleLoadedMetadata = () => {
    const audio = audioRef.current;
    if (audio) setDuration(audio.duration);
  };

  const handleEnded = () => setIsPlaying(false);

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = ratio * duration;
  };

  const formatTime = (secs: number): string => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border bg-gradient-to-r from-primary/5 to-muted/50 px-3 py-3">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />

      {/* Play/Pause button */}
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors cursor-pointer"
      >
        {isPlaying ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
      </button>

      {/* Progress area */}
      <div className="flex flex-1 flex-col gap-1">
        {/* Progress bar */}
        <div
          className="h-2 w-full cursor-pointer rounded-full bg-muted"
          onClick={handleSeek}
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
        {/* Time labels */}
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>{formatTime(currentTime)}</span>
          <span>{duration > 0 ? formatTime(duration) : "--:--"}</span>
        </div>
      </div>

      {/* Volume icon (decorative) */}
      <Volume2 size={14} className="shrink-0 text-muted-foreground" />
    </div>
  );
}

/** Human-readable section titles for each media type (Req 11.1). */
const MEDIA_TYPE_LABELS: Record<MediaType, string> = {
  text: "Text Copy",
  image: "Image Banners",
  audio: "Voiceover Audio",
  video: "Video Ads",
};

// ─── Compliance badge ────────────────────────────────────────────────────────

interface BadgeStyle {
  label: string;
  className: string;
  icon: React.ReactNode;
}

/**
 * Resolve the visual style for a compliance status. Throwing on an unexpected
 * value lets the defensive wrapper below surface the "status unavailable"
 * fallback (Req 11.4) instead of rendering a broken badge.
 */
function resolveBadgeStyle(status: ComplianceStatus): BadgeStyle {
  switch (status) {
    case "compliant":
      return {
        label: "Compliant",
        className:
          "bg-green-500/10 text-green-600 border-green-500/30 dark:text-green-400",
        icon: <CheckCircle2 size={12} />,
      };
    case "non-compliant":
      return {
        label: "Non-Compliant",
        className:
          "bg-red-500/10 text-red-600 border-red-500/30 dark:text-red-400",
        icon: <XCircle size={12} />,
      };
    case "pending":
      return {
        label: "Pending",
        className:
          "bg-amber-500/10 text-amber-600 border-amber-500/30 dark:text-amber-400",
        icon: <Clock size={12} />,
      };
    default: {
      // Exhaustiveness guard — an unexpected status triggers the fallback.
      const unexpected: never = status;
      throw new Error(`Unknown compliance status: ${String(unexpected)}`);
    }
  }
}

interface ComplianceBadgeProps {
  status: ComplianceStatus;
}

/**
 * Render a single compliance badge. Defensively wrapped so that any failure to
 * build the badge shows a "status unavailable" indicator while leaving the ad
 * itself intact (Req 11.4).
 */
function ComplianceBadge({ status }: ComplianceBadgeProps): React.ReactElement {
  try {
    const style = resolveBadgeStyle(status);
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${style.className}`}
      >
        {style.icon}
        {style.label}
      </span>
    );
  } catch {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-muted-foreground/30 bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground"
        title="Compliance status could not be displayed"
      >
        <AlertTriangle size={12} />
        Status unavailable
      </span>
    );
  }
}

// ─── Compliance reasons ──────────────────────────────────────────────────────

/** Map a risk level label to a color treatment for the reasons panel header. */
function riskLevelClass(riskLevel: string | undefined): string {
  switch ((riskLevel ?? "").toLowerCase()) {
    case "critical":
    case "high":
      return "text-red-600 dark:text-red-400";
    case "moderate":
      return "text-amber-600 dark:text-amber-400";
    case "low":
      return "text-green-600 dark:text-green-400";
    default:
      return "text-muted-foreground";
  }
}

/** True when the reasons object has at least one meaningful field to show. */
function hasReasons(reasons: ComplianceReasons | undefined): reasons is ComplianceReasons {
  if (!reasons) return false;
  return Boolean(
    reasons.explanation ||
      reasons.suggestion ||
      (reasons.indicators && reasons.indicators.length > 0) ||
      reasons.riskLevel ||
      reasons.riskPercentage !== undefined ||
      reasons.reason ||
      reasons.error
  );
}

interface ComplianceReasonsPanelProps {
  reasons: ComplianceReasons;
  status: ComplianceStatus;
}

/**
 * A collapsible "why" panel explaining a compliance verdict — risk level,
 * explanation, flagged indicators, and the suggested fix. Collapsed by default
 * to keep the card compact; expands on click. Defaults open for non-compliant
 * ads so the blocking reason is immediately visible.
 */
function ComplianceReasonsPanel({
  reasons,
  status,
}: ComplianceReasonsPanelProps): React.ReactElement {
  const [open, setOpen] = useState(status === "non-compliant");

  return (
    <div className="rounded-md border bg-muted/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-[11px] font-semibold text-foreground hover:bg-muted/60 transition-colors cursor-pointer"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1.5">
          <Info size={12} className="text-muted-foreground" />
          Why this verdict
          {reasons.riskLevel && (
            <span className={`font-bold ${riskLevelClass(reasons.riskLevel)}`}>
              · {reasons.riskLevel}
              {reasons.riskPercentage !== undefined ? ` (${reasons.riskPercentage}%)` : ""}
            </span>
          )}
        </span>
        <ChevronDown
          size={14}
          className={`shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="flex flex-col gap-2 border-t px-2.5 py-2 text-[11px] leading-relaxed">
          {reasons.skipped && (
            <p className="text-muted-foreground italic">
              Compliance check was skipped
              {reasons.reason ? `: ${reasons.reason}` : "."}
            </p>
          )}

          {reasons.error && (
            <p className="flex items-start gap-1.5 text-amber-600 dark:text-amber-400">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>{reasons.error}</span>
            </p>
          )}

          {reasons.explanation && (
            <p className="text-foreground">{reasons.explanation}</p>
          )}

          {reasons.indicators && reasons.indicators.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="font-semibold text-muted-foreground">Flagged items</span>
              <ul className="flex flex-col gap-0.5">
                {reasons.indicators.map((indicator, idx) => (
                  <li key={idx} className="flex items-start gap-1.5 text-foreground">
                    <XCircle size={11} className="mt-0.5 shrink-0 text-red-500" />
                    <span>{indicator}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {reasons.suggestion && (
            <p className="flex items-start gap-1.5 rounded bg-primary/5 px-2 py-1.5 text-foreground">
              <Lightbulb size={12} className="mt-0.5 shrink-0 text-primary" />
              <span>
                <span className="font-semibold">Suggested fix: </span>
                {reasons.suggestion}
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Media preview ───────────────────────────────────────────────────────────

interface MediaPreviewProps {
  ad: GeneratedAdView;
}

/** Render the ad's media by type: image thumbnail, audio/video player, or text. */
function MediaPreview({ ad }: MediaPreviewProps): React.ReactElement {
  const { mediaType, publicUrl, caption } = ad;

  if (mediaType === "text") {
    return (
      <div className="flex min-h-24 items-start gap-2 rounded-md bg-muted/50 p-3 text-sm text-foreground">
        <FileText size={14} className="mt-0.5 shrink-0 text-muted-foreground" />
        <p className="whitespace-pre-wrap leading-relaxed">
          {caption ?? "No caption provided."}
        </p>
      </div>
    );
  }

  if (publicUrl === null) {
    return (
      <div className="flex min-h-24 items-center justify-center gap-2 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
        <ImageIcon size={14} />
        Media unavailable
      </div>
    );
  }

  if (mediaType === "image") {
    return (
      <img
        src={publicUrl}
        alt={caption ?? "Generated image ad"}
        className="h-40 w-full rounded-md object-cover"
        loading="lazy"
      />
    );
  }

  if (mediaType === "audio") {
    return <AudioPlayer src={publicUrl} />;
  }

  // video
  return (
    <video
      controls
      src={publicUrl}
      className="h-40 w-full rounded-md bg-black object-contain"
    >
      Your browser does not support the video element.
    </video>
  );
}

// ─── Output card ─────────────────────────────────────────────────────────────

interface OutputCardProps {
  ad: GeneratedAdView;
  pendingCleared: boolean;
  onClearPending: (adId: string) => void;
  projectId?: string;
  taskId?: string;
}

/** Publish-gate button states for one output. */
type PublishPhase = "idle" | "publishing" | "published" | "error";
type DistributePhase = "idle" | "distributing" | "distributed" | "error";

/**
 * A single generated output. Shows the media, a compliance badge, and — while
 * the output is pending and the user has not dismissed it — a persistent
 * pending indicator with a dismiss control (Req 11.3). When project/task
 * context is available, it also exposes the human-in-the-loop Publish gate:
 * the owner reviews the output and clicks Publish to approve it. Ads that
 * failed compliance are blocked from publishing.
 */
function OutputCard({
  ad,
  pendingCleared,
  onClearPending,
  projectId,
  taskId,
}: OutputCardProps): React.ReactElement {
  const showPendingIndicator =
    ad.complianceStatus === "pending" && !pendingCleared;

  const [publishPhase, setPublishPhase] = useState<PublishPhase>("idle");
  const [publishError, setPublishError] = useState<string | null>(null);
  const [distributePhase, setDistributePhase] = useState<DistributePhase>("idle");
  const [distributeError, setDistributeError] = useState<string | null>(null);

  const canPublish =
    projectId !== undefined &&
    taskId !== undefined &&
    ad.adId !== "" &&
    ad.complianceStatus !== "non-compliant";

  const handlePublish = async (): Promise<void> => {
    if (projectId === undefined || taskId === undefined) return;
    setPublishPhase("publishing");
    setPublishError(null);
    try {
      await publishAd(projectId, taskId, ad.adId);
      setPublishPhase("published");
    } catch (err) {
      setPublishPhase("error");
      setPublishError(err instanceof Error ? err.message : "Publish failed");
    }
  };

  const handleDistribute = async (): Promise<void> => {
    if (projectId === undefined || taskId === undefined) return;
    setDistributePhase("distributing");
    setDistributeError(null);
    try {
      await distributeAd(projectId, taskId, ad.adId, ad.platform || "tiktok");
      setDistributePhase("distributed");
    } catch (err) {
      setDistributePhase("error");
      setDistributeError(err instanceof Error ? err.message : "Distribution failed");
    }
  };

  return (
    <div className="output-card flex flex-col gap-2 rounded-lg border bg-card p-3 shadow-sm">
      <MediaPreview ad={ad} />

      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {ad.platform}
        </span>
        <ComplianceBadge status={ad.complianceStatus} />
      </div>

      {ad.mediaType !== "text" && ad.caption !== null && (
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {ad.caption}
        </p>
      )}

      {/* Why this compliance verdict — risk, explanation, indicators, fix */}
      {hasReasons(ad.complianceReasons) && (
        <ComplianceReasonsPanel
          reasons={ad.complianceReasons}
          status={ad.complianceStatus}
        />
      )}

      {showPendingIndicator && (
        <div className="flex items-center justify-between gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-600 dark:text-amber-400">
          <span className="flex items-center gap-1">
            <Clock size={12} />
            Compliance review pending
          </span>
          <button
            type="button"
            onClick={() => onClearPending(ad.adId)}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-semibold hover:bg-amber-500/20 transition-colors cursor-pointer"
            title="Dismiss pending indicator"
          >
            <X size={12} />
            Dismiss
          </button>
        </div>
      )}

      {/* Human-in-the-loop publish gate */}
      {canPublish && publishPhase !== "published" && (
        <button
          type="button"
          onClick={handlePublish}
          disabled={publishPhase === "publishing"}
          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
          title="Approve and publish this ad"
        >
          {publishPhase === "publishing" ? (
            <>
              <Loader2 size={12} className="animate-spin" />
              Publishing...
            </>
          ) : (
            <>
              <Rocket size={12} />
              {publishPhase === "error" ? "Retry Publish" : "Publish"}
            </>
          )}
        </button>
      )}

      {publishPhase === "published" && (
        <span className="inline-flex items-center justify-center gap-1.5 rounded-md border border-green-500/30 bg-green-500/10 px-2.5 py-1.5 text-xs font-semibold text-green-600 dark:text-green-400">
          <CheckCircle2 size={12} />
          Published
        </span>
      )}

      {/* Distribute button — only shows after publish */}
      {publishPhase === "published" && distributePhase !== "distributed" && (
        <button
          type="button"
          onClick={handleDistribute}
          disabled={distributePhase === "distributing"}
          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
          title={`Distribute to ${ad.platform || "TikTok"}`}
        >
          {distributePhase === "distributing" ? (
            <>
              <Loader2 size={12} className="animate-spin" />
              Distributing...
            </>
          ) : (
            <>
              <Send size={12} />
              {distributePhase === "error" ? "Retry Distribute" : `Distribute → ${(ad.platform || "TikTok").charAt(0).toUpperCase() + (ad.platform || "tiktok").slice(1)}`}
            </>
          )}
        </button>
      )}

      {distributePhase === "distributed" && (
        <span className="inline-flex items-center justify-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2.5 py-1.5 text-xs font-semibold text-blue-600 dark:text-blue-400">
          <Send size={12} />
          Distributed
        </span>
      )}

      {distributePhase === "error" && distributeError !== null && (
        <p className="text-[11px] text-red-600 dark:text-red-400">
          {distributeError}
        </p>
      )}

      {ad.complianceStatus === "non-compliant" && (
        <span
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1.5 text-[11px] font-medium text-red-600 dark:text-red-400"
          title="Non-compliant ads cannot be published"
        >
          <AlertTriangle size={12} />
          Blocked — resolve compliance to publish
        </span>
      )}

      {publishPhase === "error" && publishError !== null && (
        <p className="text-[11px] text-red-600 dark:text-red-400">
          {publishError}
        </p>
      )}
    </div>
  );
}

// ─── Gallery ─────────────────────────────────────────────────────────────────

/**
 * Output gallery: renders outputs grouped by media-type section, with a
 * per-output compliance badge and a dismissible pending indicator.
 */
export function OutputGallery({ ads, isSidebar, projectId, taskId }: OutputGalleryProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [clearedPending, setClearedPending] = useState<Set<string>>(new Set());

  const grouped = groupAdsByMediaType(ads);

  useGSAP(
    () => {
      gsap.from(".output-card", {
        y: 30,
        autoAlpha: 0,
        stagger: 0.08,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [ads.length] }
  );

  const clearPending = (adId: string): void => {
    setClearedPending((prev) => {
      const next = new Set(prev);
      next.add(adId);
      return next;
    });
  };

  const hasOutputs = ads.length > 0;
  const gridClass = isSidebar
    ? "grid grid-cols-1 gap-3"
    : "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3";

  return (
    <div ref={containerRef} className="flex h-full flex-col gap-6 overflow-y-auto p-4">
      {!hasOutputs && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          No generated outputs yet.
        </div>
      )}

      {MEDIA_TYPES.filter((mediaType) => grouped[mediaType].length > 0).map(
        (mediaType) => (
          <section key={mediaType} className="flex flex-col gap-3">
            <h3 className="text-sm font-bold text-primary">
              {MEDIA_TYPE_LABELS[mediaType]}
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                ({grouped[mediaType].length})
              </span>
            </h3>
            <div className={gridClass}>
              {grouped[mediaType].map((ad) => (
                <OutputCard
                  key={ad.adId}
                  ad={ad}
                  pendingCleared={clearedPending.has(ad.adId)}
                  onClearPending={clearPending}
                  projectId={projectId}
                  taskId={taskId}
                />
              ))}
            </div>
          </section>
        )
      )}
    </div>
  );
}

export default OutputGallery;
