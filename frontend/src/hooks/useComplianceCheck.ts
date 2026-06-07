import { useState, useCallback, useRef } from "react";
import type { UploadParams } from "@/types/compliance";
import type {
  NodeStatus,
  ComplianceResult,
  StreamEvent,
} from "@/services/complianceApi";
import { API_BASE } from "@/services/complianceApi";

export interface UseComplianceCheckReturn {
  submit: (params: UploadParams) => Promise<ComplianceResult>;
  isStreaming: boolean;
  nodeStatuses: NodeStatus[];
  currentNode: string | null;
  error: { message: string; retryable: boolean } | null;
  retry: () => void;
}

/**
 * Custom hook that encapsulates SSE streaming logic for compliance checks.
 * Submits multipart/form-data to POST /api/compliance/check, reads the SSE
 * stream via ReadableStream reader, and tracks node status updates in state.
 */
export function useComplianceCheck(): UseComplianceCheckReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [nodeStatuses, setNodeStatuses] = useState<NodeStatus[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [error, setError] = useState<{
    message: string;
    retryable: boolean;
  } | null>(null);

  const lastParamsRef = useRef<UploadParams | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const errorSetRef = useRef(false);

  const submit = useCallback(
    async (params: UploadParams): Promise<ComplianceResult> => {
      // Store params for retry
      lastParamsRef.current = params;

      // Reset state
      setIsStreaming(true);
      setNodeStatuses([]);
      setCurrentNode(null);
      setError(null);
      errorSetRef.current = false;

      // Abort any previous in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Construct FormData
      const formData = new FormData();
      if (params.file) {
        formData.append("file", params.file);
      } else if (params.text) {
        formData.append("text", params.text);
      }
      formData.append("market", params.market);
      formData.append("ethnicity", params.ethnicity);
      formData.append("age_group", params.ageGroup);

      try {
        const res = await fetch(`${API_BASE}/api/compliance/check`, {
          method: "POST",
          body: formData,
          signal: abortController.signal,
        });

        if (!res.ok) {
          const retryable = res.status >= 500;
          const message =
            res.status === 400
              ? "Validation error: please provide a file or text"
              : `Server error (${res.status})`;
          setError({ message, retryable });
          errorSetRef.current = true;
          setIsStreaming(false);
          throw new Error(message);
        }

        // Read SSE stream via ReadableStream reader
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let finalResult: ComplianceResult | null = null;
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event = JSON.parse(line.slice(6)) as StreamEvent;

                if (event.type === "node_status") {
                  setNodeStatuses((prev) => [...prev, event]);
                  setCurrentNode(event.node);
                } else if (event.type === "result") {
                  finalResult = event.data;
                }
              } catch {
                // Skip malformed SSE lines
              }
            }
          }
        }

        if (!finalResult) {
          setError({
            message: "Stream ended without a result. The check may be incomplete.",
            retryable: true,
          });
          errorSetRef.current = true;
          setIsStreaming(false);
          throw new Error("Stream ended without result");
        }

        setIsStreaming(false);
        return finalResult;
      } catch (err: unknown) {
        setIsStreaming(false);

        // Don't overwrite error state if already set (e.g. from HTTP status handling)
        if (err instanceof DOMException && err.name === "AbortError") {
          // Request was aborted, don't set error
          throw err;
        }

        if (!errorSetRef.current) {
          const message =
            err instanceof Error ? err.message : "Connection failed";
          setError({ message, retryable: true });
        }

        throw err;
      }
    },
    []
  );

  const retry = useCallback(() => {
    if (lastParamsRef.current) {
      submit(lastParamsRef.current);
    }
  }, [submit]);

  return {
    submit,
    isStreaming,
    nodeStatuses,
    currentNode,
    error,
    retry,
  };
}
