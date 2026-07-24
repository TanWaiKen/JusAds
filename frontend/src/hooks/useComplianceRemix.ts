import { useState, useCallback, useRef } from "react";
import type {
  RemixNodeStatus,
  RemixStreamEvent,
  RemixCannotFixEvent,
  RemixImageEditEvent,
  RemixEditFailedEvent,
  RemediationResult,
} from "@/services/remix";
import { streamRemix } from "@/services/remix";

export type RemixOutcome = "compliant" | "cannot_fix" | "image_edit" | "edit_failed" | null;

export interface UseComplianceRemixReturn {
  startRemix: (checkId: string) => Promise<RemediationResult | null>;
  isRemixing: boolean;
  remixNodes: RemixNodeStatus[];
  currentNode: string | null;
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
  const [remixNodes, setRemixNodes] = useState<RemixNodeStatus[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [remixComplete, setRemixComplete] = useState(false);
  const [remixError, setRemixError] = useState<string | null>(null);

  // New triage outcome states
  const [remixOutcome, setRemixOutcome] = useState<RemixOutcome>(null);
  const [cannotFixData, setCannotFixData] = useState<RemixCannotFixEvent | null>(null);
  const [imageEditResult, setImageEditResult] = useState<RemixImageEditEvent | null>(null);
  const [editFailedData, setEditFailedData] = useState<RemixEditFailedEvent | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const startRemix = useCallback(async (checkId: string) => {
    setIsRemixing(true);
    setRemixNodes([]);
    setCurrentNode(null);
    setRemixComplete(false);
    setRemixError(null);
    setRemixOutcome(null);
    setCannotFixData(null);
    setImageEditResult(null);
    setEditFailedData(null);

    let completedResult: RemediationResult | null = null;
    let streamFailure: string | null = null;
    let receivedTerminalEvent = false;
    let controller: AbortController | null = null;
    try {
      abortRef.current?.abort();
      controller = new AbortController();
      abortRef.current = controller;
      await streamRemix(checkId, (event: RemixStreamEvent) => {
        console.log("[Remix] SSE event:", event);
        switch (event.type) {
          case "node_status":
            setRemixNodes((prev) => {
              const existing = prev.findIndex((node) => node.node === event.node);
              if (existing < 0) return [...prev, event];
              const updated = [...prev];
              updated[existing] = event;
              return updated;
            });
            if (event.status === "running") setCurrentNode(event.node);
            if (event.status === "error") {
              streamFailure = event.description;
              setRemixError(streamFailure);
            }
            break;
          case "remix_result":
            completedResult = event.data ?? null;
            receivedTerminalEvent = true;
            setRemixComplete(true);
            break;
          case "compliant":
            receivedTerminalEvent = true;
            setRemixOutcome("compliant");
            setRemixComplete(true);
            break;
          case "cannot_fix":
            receivedTerminalEvent = true;
            setRemixOutcome("cannot_fix");
            setCannotFixData(event);
            setRemixComplete(true);
            break;
          case "image_edit":
            receivedTerminalEvent = true;
            setRemixOutcome("image_edit");
            setImageEditResult(event);
            setRemixComplete(true);
            break;
          case "edit_failed":
            receivedTerminalEvent = true;
            setRemixOutcome("edit_failed");
            setEditFailedData(event);
            setRemixComplete(true);
            break;
          case "error":
            streamFailure = event.message;
            setRemixError(streamFailure);
            break;
        }
      }, controller.signal);

      if (streamFailure) throw new Error(streamFailure);
      if (!receivedTerminalEvent) {
        throw new Error("Remix stream ended without a remediation result.");
      }
      setRemixComplete(true);
      return completedResult;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Remix failed";
      setRemixError(message);
      throw err;
    } finally {
      setIsRemixing(false);
      setCurrentNode(null);
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, []);

  const reset = useCallback(() => {
    setIsRemixing(false);
    setRemixNodes([]);
    setCurrentNode(null);
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
    currentNode,
    remixComplete,
    remixError,
    remixOutcome,
    cannotFixData,
    imageEditResult,
    editFailedData,
    reset,
  };
}
