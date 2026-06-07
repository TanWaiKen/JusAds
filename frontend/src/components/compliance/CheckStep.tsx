import type { NodeStatus } from "@/services/complianceApi";
import { PipelineStatusIndicator } from "@/components/compliance/PipelineStatusIndicator";
import { Button } from "@/components/ui/button";

interface CheckStepProps {
  nodeStatuses: NodeStatus[];
  currentNode: string | null;
  isStreaming: boolean;
  mediaType: string;
  error: { message: string; retryable: boolean } | null;
  onRetry: () => void;
}

/**
 * CheckStep renders the compliance pipeline progress during streaming
 * and displays error state with retry capability when the stream fails.
 *
 * Includes an aria-live region to announce node status changes to screen readers.
 */
export function CheckStep({
  nodeStatuses,
  currentNode,
  isStreaming,
  mediaType,
  error,
  onRetry,
}: CheckStepProps) {
  // Determine the latest node status for the aria-live announcement
  const latestNodeStatus = nodeStatuses.length > 0
    ? nodeStatuses[nodeStatuses.length - 1]
    : null;

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {/* Pipeline progress indicator */}
      <PipelineStatusIndicator
        nodeStatuses={nodeStatuses}
        currentNode={currentNode}
        isStreaming={isStreaming}
        mediaType={mediaType}
      />

      {/* Visually hidden aria-live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {latestNodeStatus &&
          `${latestNodeStatus.description}: ${latestNodeStatus.status}`}
      </div>

      {/* Error state with retry button */}
      {error && (
        <div
          className="p-4 bg-error-container rounded-xl flex items-center justify-between w-full max-w-lg"
          role="alert"
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-on-error-container">
              error
            </span>
            <p className="text-on-error-container font-label-ui text-label-ui">
              {error.message}
            </p>
          </div>
          {error.retryable && (
            <Button onClick={onRetry} variant="default" size="sm">
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
