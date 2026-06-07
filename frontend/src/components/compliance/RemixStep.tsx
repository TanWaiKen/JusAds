import type { NodeStatus } from "@/services/complianceApi";
import { PipelineStatusIndicator } from "@/components/compliance/PipelineStatusIndicator";
import { Button } from "@/components/ui/button";

interface RemixStepProps {
  remixNodes: NodeStatus[];
  isRemixing: boolean;
  remixComplete: boolean;
  remixError: string | null;
  onRetry: () => void;
}

/**
 * RemixStep renders the remix pipeline progress during streaming
 * and displays error state with retry capability when the remix stream fails.
 * Shows a success indicator when the remix completes.
 *
 * Includes an aria-live region to announce node status changes to screen readers.
 */
export function RemixStep({
  remixNodes,
  isRemixing,
  remixComplete,
  remixError,
  onRetry,
}: RemixStepProps) {
  // Determine the latest node status for the aria-live announcement
  const latestNodeStatus =
    remixNodes.length > 0 ? remixNodes[remixNodes.length - 1] : null;

  // Derive currentNode from the latest running node
  const currentNode =
    remixNodes.find((n) => n.status === "running")?.node ?? null;

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {/* Pipeline progress indicator (reuses same component as CheckStep) */}
      <PipelineStatusIndicator
        nodeStatuses={remixNodes}
        currentNode={currentNode}
        isStreaming={isRemixing}
        mediaType="video"
      />

      {/* Visually hidden aria-live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {latestNodeStatus &&
          `${latestNodeStatus.description}: ${latestNodeStatus.status}`}
      </div>

      {/* Success state when remix completes */}
      {remixComplete && (
        <div className="flex items-center gap-3 p-4 bg-emerald-glow/10 rounded-xl">
          <span className="material-symbols-outlined text-emerald-glow">
            check_circle
          </span>
          <p className="text-emerald-glow font-label-ui text-label-ui">
            Remix complete
          </p>
        </div>
      )}

      {/* Error state with retry button */}
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
