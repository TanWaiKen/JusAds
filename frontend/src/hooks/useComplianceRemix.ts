import { useState, useCallback } from "react";
import type { NodeStatus, RemixStreamEvent } from "@/services/complianceApi";
import { remixComplianceStream } from "@/services/complianceApi";

export interface UseComplianceRemixReturn {
  startRemix: (checkId: string) => Promise<void>;
  isRemixing: boolean;
  remixNodes: NodeStatus[];
  remixComplete: boolean;
  remixError: string | null;
  reset: () => void;
}

/**
 * Custom hook for triggering and tracking the AI auto-remix process.
 * Streams SSE events from POST /api/compliance/{checkId}/remix.
 */
export function useComplianceRemix(): UseComplianceRemixReturn {
  const [isRemixing, setIsRemixing] = useState(false);
  const [remixNodes, setRemixNodes] = useState<NodeStatus[]>([]);
  const [remixComplete, setRemixComplete] = useState(false);
  const [remixError, setRemixError] = useState<string | null>(null);

  const startRemix = useCallback(async (checkId: string) => {
    setIsRemixing(true);
    setRemixNodes([]);
    setRemixComplete(false);
    setRemixError(null);

    try {
      await remixComplianceStream(checkId, (event: RemixStreamEvent) => {
        if (event.type === "node_status") {
          setRemixNodes((prev) => [...prev, event]);
        } else if (event.type === "remix_result") {
          setRemixComplete(true);
        }
      });

      // If stream ends without explicit remix_result, still mark complete
      setRemixComplete(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Remix failed";
      setRemixError(message);
    } finally {
      setIsRemixing(false);
    }
  }, []);

  const reset = useCallback(() => {
    setIsRemixing(false);
    setRemixNodes([]);
    setRemixComplete(false);
    setRemixError(null);
  }, []);

  return {
    startRemix,
    isRemixing,
    remixNodes,
    remixComplete,
    remixError,
    reset,
  };
}
