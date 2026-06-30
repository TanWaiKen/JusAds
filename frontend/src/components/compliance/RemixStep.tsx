import type { NodeStatus, RemixCannotFixEvent, RemixImageEditEvent, RemixEditFailedEvent } from "@/services/complianceApi";
import type { RemixOutcome } from "@/hooks/useComplianceRemix";
import { PipelineStatusIndicator } from "@/components/compliance/PipelineStatusIndicator";
import { Button } from "@/components/ui/button";

interface RemixStepProps {
  remixNodes: NodeStatus[];
  isRemixing: boolean;
  remixComplete: boolean;
  remixError: string | null;
  remixOutcome: RemixOutcome;
  cannotFixData: RemixCannotFixEvent | null;
  imageEditResult: RemixImageEditEvent | null;
  editFailedData: RemixEditFailedEvent | null;
  onRetry: () => void;
  mediaType: "text" | "image" | "audio" | "video";
}

/**
 * RemixStep renders the remix pipeline progress during streaming
 * and displays specific outcome panels when the remix stream completes.
 *
 * Includes an aria-live region to announce node status changes to screen readers.
 */
export function RemixStep({
  remixNodes,
  isRemixing,
  remixComplete,
  remixError,
  remixOutcome,
  cannotFixData,
  imageEditResult,
  editFailedData,
  onRetry,
  mediaType,
}: RemixStepProps) {
  // Determine the latest node status for the aria-live announcement
  const latestNodeStatus =
    remixNodes.length > 0 ? remixNodes[remixNodes.length - 1] : null;

  // Derive currentNode from the latest running node
  const currentNode =
    remixNodes.find((n) => n.status === "running")?.node ?? null;

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {/* Pipeline progress indicator */}
      <PipelineStatusIndicator
        nodeStatuses={remixNodes}
        currentNode={currentNode}
        isStreaming={isRemixing}
        mediaType={mediaType}
      />

      {/* Visually hidden aria-live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {latestNodeStatus &&
          `${latestNodeStatus.description}: ${latestNodeStatus.status}`}
      </div>

      {/* Success states when remix completes */}
      {remixComplete && !remixError && (
        <div className="w-full max-w-2xl flex flex-col gap-4">
          {/* OUTCOME: COMPLIANT */}
          {remixOutcome === "compliant" && (
            <div className="flex items-center gap-3 p-4 bg-emerald-glow/10 rounded-xl border border-emerald-glow/20">
              <span className="material-symbols-outlined text-emerald-glow">check_circle</span>
              <div>
                <p className="text-emerald-glow font-label-ui text-label-ui font-semibold">Image Passes Compliance</p>
                <p className="text-text-muted text-sm mt-1">No remediation is required for this image.</p>
              </div>
            </div>
          )}

          {/* OUTCOME: CANNOT_FIX */}
          {remixOutcome === "cannot_fix" && cannotFixData && (
            <div className="flex flex-col gap-3 p-4 bg-amber-500/10 rounded-xl border border-amber-500/20">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-amber-500">warning</span>
                <p className="text-amber-500 font-label-ui text-label-ui font-semibold">Manual Fix Required</p>
              </div>
              <p className="text-text-body text-sm">{cannotFixData.guidance}</p>
              {cannotFixData.reasoning && (
                <p className="text-text-muted text-xs bg-surface-inset p-2 rounded-lg mt-1 border border-outline-variant">
                  {cannotFixData.reasoning}
                </p>
              )}
            </div>
          )}

          {/* OUTCOME: IMAGE_EDIT */}
          {remixOutcome === "image_edit" && imageEditResult && (
            <div className="flex flex-col gap-3 p-4 bg-emerald-glow/10 rounded-xl border border-emerald-glow/20">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-emerald-glow">auto_fix_high</span>
                <p className="text-emerald-glow font-label-ui text-label-ui font-semibold">AI Edit Complete</p>
              </div>
              
              <div className="flex flex-col gap-2 mt-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-text-muted">Quality Score:</span>
                  <span className={`font-semibold ${imageEditResult.quality_score >= 80 ? 'text-emerald-500' : 'text-amber-500'}`}>
                    {imageEditResult.quality_score}/100
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-text-muted">Edit Mode:</span>
                  <span className="text-text-body">{imageEditResult.edit_mode}</span>
                </div>
                
                {/* Bias Check Results */}
                {imageEditResult.bias_check && (
                  <div className={`mt-3 p-3 rounded-lg border ${imageEditResult.bias_check.passed ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-error-container/50 border-error-container/80'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`material-symbols-outlined text-sm ${imageEditResult.bias_check.passed ? 'text-emerald-500' : 'text-on-error-container'}`}>
                        {imageEditResult.bias_check.passed ? 'verified_user' : 'gpp_maybe'}
                      </span>
                      <p className={`text-xs font-semibold ${imageEditResult.bias_check.passed ? 'text-emerald-500' : 'text-on-error-container'}`}>
                        Bias & Safety Check: {imageEditResult.bias_check.passed ? 'PASSED' : 'FLAGGED'}
                      </p>
                    </div>
                    
                    {!imageEditResult.bias_check.passed && imageEditResult.bias_check.issues.length > 0 && (
                      <ul className="list-disc list-inside text-xs text-on-error-container space-y-1 ml-1 mt-2">
                        {imageEditResult.bias_check.issues.map((issue, idx) => (
                          <li key={idx}>{issue}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* OUTCOME: EDIT_FAILED */}
          {remixOutcome === "edit_failed" && editFailedData && (
            <div className="flex flex-col gap-3 p-4 bg-error-container/80 rounded-xl border border-error-container">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-on-error-container">error</span>
                <p className="text-on-error-container font-label-ui text-label-ui font-semibold">AI Edit Failed</p>
              </div>
              <p className="text-sm text-on-error-container mt-1">{editFailedData.fallback_guidance}</p>
              <p className="text-xs text-on-error-container/80 mt-2 bg-on-error-container/10 p-2 rounded-lg">
                Error: {editFailedData.error}
              </p>
              <Button onClick={onRetry} variant="default" size="sm" className="mt-2 self-start bg-on-error-container text-error-container hover:bg-on-error-container/90">
                Retry Edit
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Global Error state with retry button */}
      {remixError && (
        <div
          className="p-4 bg-error-container rounded-xl flex items-center justify-between w-full max-w-lg"
          role="alert"
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-on-error-container">
              error
            </span>
            <p className="text-on-error-container font-label-ui text-label-ui">
              {remixError}
            </p>
          </div>
          <Button onClick={onRetry} variant="default" size="sm">
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
