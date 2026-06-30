import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { NodeStatus } from "@/services/complianceApi";
import { Button } from "@/components/ui/button";

gsap.registerPlugin(useGSAP);

interface CheckStepProps {
  nodeStatuses: NodeStatus[];
  currentNode: string | null;
  isStreaming: boolean;
  mediaType: string;
  error: { message: string; retryable: boolean } | null;
  onRetry: () => void;
}

/** Human-readable labels and descriptions for pipeline nodes */
const NODE_INFO: Record<string, { label: string; icon: string }> = {
  compliance_check: { label: "Compliance Analysis", icon: "🔍" },
  segment_image: { label: "Image Segmentation", icon: "🖼️" },
  extract_clips: { label: "Video Clip Extraction", icon: "🎬" },
  verify_violations: { label: "Violation Verification", icon: "🔎" },
  judge_hallucination: { label: "Bias & Hallucination Check", icon: "⚖️" },
  __interrupt__: { label: "Human Review", icon: "👤" },
  human_review: { label: "Human Review", icon: "👤" },
  finalize: { label: "Finalizing", icon: "📋" },
  remix_router: { label: "Remix Routing", icon: "🔄" },
  remix_finalize: { label: "Remix Validation", icon: "✨" },
  // Legacy node names
  post_process: { label: "Post Processing", icon: "⚙️" },
  router: { label: "Routing", icon: "🔀" },
  image_check: { label: "Image Analysis", icon: "🖼️" },
  video_check: { label: "Video Analysis", icon: "🎬" },
  text_check: { label: "Text Analysis", icon: "📝" },
  transcribe: { label: "Transcription", icon: "🎤" },
};

function getNodeInfo(nodeName: string): { label: string; icon: string } {
  if (nodeName === "progress") return { label: "Progress", icon: "📌" };
  return NODE_INFO[nodeName] ?? { label: nodeName.replace(/_/g, " "), icon: "⚙️" };
}

/**
 * CheckStep shows a live activity log during compliance pipeline execution.
 * Each WebSocket event appears as a timestamped entry with animated entrance.
 */
export function CheckStep({
  nodeStatuses,
  currentNode: _currentNode,
  isStreaming,
  mediaType,
  error,
  onRetry,
}: CheckStepProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const items = containerRef.current?.querySelectorAll(".log-entry");
      if (items && items.length > 0) {
        gsap.from(items[items.length - 1], {
          y: 10,
          opacity: 0,
          duration: 0.3,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [nodeStatuses.length] }
  );

  return (
    <div ref={containerRef} className="flex flex-col items-center gap-6 py-8 w-full max-w-lg mx-auto">
      {/* Header */}
      <div className="flex flex-col items-center gap-2">
        {isStreaming && (
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-sm font-medium text-text-primary">Processing {mediaType} compliance check...</span>
          </div>
        )}
        {!isStreaming && !error && nodeStatuses.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-emerald-600 dark:text-emerald-400">Complete</span>
          </div>
        )}
      </div>

      {/* Activity Log — fixed height scrollable area */}
      {nodeStatuses.length > 0 && (
        <div className="w-full rounded-xl border bg-surface-card p-4 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Pipeline Activity</h3>
          <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
            {nodeStatuses.map((ns, i) => {
              const info = getNodeInfo(ns.node);
              const isLast = i === nodeStatuses.length - 1;
              const isActive = isLast && isStreaming;

              return (
                <div
                  key={`${ns.node}-${i}`}
                  className={`log-entry flex items-start gap-3 transition-colors ${
                    ns.node === "progress"
                      ? "pl-8 py-1.5"
                      : `p-2.5 rounded-lg ${isActive ? "bg-blue-500/5 border border-blue-500/20" : "bg-surface-inset/50"}`
                  }`}
                >
                  {/* Status icon */}
                  <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${
                    ns.status === "completed"
                      ? "bg-emerald-100 dark:bg-emerald-900/30"
                      : ns.status === "error"
                        ? "bg-red-100 dark:bg-red-900/30"
                        : "bg-blue-100 dark:bg-blue-900/30"
                  }`}>
                    {ns.status === "completed" ? "✓" : ns.status === "error" ? "✗" : info.icon}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{info.label}</span>
                      <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                        ns.status === "completed"
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                          : ns.status === "error"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                            : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      }`}>
                        {ns.status}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 truncate">{ns.description}</p>
                  </div>
                </div>
              );
            })}

            {/* Waiting indicator for next node */}
            {isStreaming && (
              <div className="log-entry flex items-center gap-3 p-2.5 rounded-lg bg-surface-inset/30">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-inset">
                  <div className="h-2 w-2 rounded-full bg-text-muted animate-pulse" />
                </div>
                <span className="text-xs text-text-muted italic">Waiting for next step...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state — before any events arrive */}
      {nodeStatuses.length === 0 && isStreaming && (
        <div className="w-full rounded-xl border bg-surface-card p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-blue-500/10 flex items-center justify-center">
            <div className="h-3 w-3 rounded-full bg-blue-500 animate-pulse" />
          </div>
          <p className="text-sm text-text-muted">Connecting to compliance pipeline...</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="w-full p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-center justify-between" role="alert">
          <div className="flex items-center gap-3">
            <span className="text-red-500 text-lg">⚠️</span>
            <p className="text-sm text-red-700 dark:text-red-300">{error.message}</p>
          </div>
          {error.retryable && (
            <Button onClick={onRetry} variant="default" size="sm">Retry</Button>
          )}
        </div>
      )}

      {/* Accessibility */}
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {nodeStatuses.length > 0 && `${nodeStatuses[nodeStatuses.length - 1].description}: ${nodeStatuses[nodeStatuses.length - 1].status}`}
      </div>
    </div>
  );
}
