import { useState, useCallback } from "react";
import type {
  NodeStatus,
  RemixStreamEvent,
  RemixCannotFixEvent,
  RemixImageEditEvent,
  RemixEditFailedEvent,
} from "@/services/complianceApi";
import { remixComplianceStream } from "@/services/complianceApi";

export type RemixOutcome = "compliant" | "cannot_fix" | "image_edit" | "edit_failed" | null;

export interface UseComplianceRemixReturn {
  startRemix: (checkId: string) => Promise<void>;
  isRemixing: boolean;
  remixNodes: NodeStatus[];
  remixComplete: boolean;
  remixError: string | null;
  remixOutcome: RemixOutcome;
  cannotFixData: RemixCannotFixEvent | null;
  imageEditResult: RemixImageEditEvent | null;
  editFailedData: RemixEditFailedEvent | null;
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

  // New triage outcome states
  const [remixOutcome, setRemixOutcome] = useState<RemixOutcome>(null);
  const [cannotFixData, setCannotFixData] = useState<RemixCannotFixEvent | null>(null);
  const [imageEditResult, setImageEditResult] = useState<RemixImageEditEvent | null>(null);
  const [editFailedData, setEditFailedData] = useState<RemixEditFailedEvent | null>(null);

  const startRemix = useCallback(async (checkId: string) => {
    setIsRemixing(true);
    setRemixNodes([]);
    setRemixComplete(false);
    setRemixError(null);
    setRemixOutcome(null);
    setCannotFixData(null);
    setImageEditResult(null);
    setEditFailedData(null);

    try {
      await remixComplianceStream(checkId, (event: RemixStreamEvent) => {
        console.log("[Remix] SSE event:", event);
        switch (event.type) {
          case "node_status":
            setRemixNodes((prev) => [...prev, event]);
            break;
          case "remix_result":
            setRemixComplete(true);
            break;
          case "compliant":
            setRemixOutcome("compliant");
            setRemixComplete(true);
            break;
          case "cannot_fix":
            setRemixOutcome("cannot_fix");
            setCannotFixData(event);
            setRemixComplete(true);
            break;
          case "image_edit":
            setRemixOutcome("image_edit");
            setImageEditResult(event);
            setRemixComplete(true);
            break;
          case "edit_failed":
            setRemixOutcome("edit_failed");
            setEditFailedData(event);
            setRemixComplete(true);
            break;
          case "error":
            setRemixError(event.message);
            // Don't stop streaming on standard errors unless it closes
            break;
        }
      });

      // If stream ends without explicit completion flag, mark it
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
    setRemixOutcome(null);
    setCannotFixData(null);
    setImageEditResult(null);
    setEditFailedData(null);
  }, []);

  return {
    startRemix,
    isRemixing,
    remixNodes,
    remixComplete,
    remixError,
    remixOutcome,
    cannotFixData,
    imageEditResult,
    editFailedData,
    reset,
  };
}
