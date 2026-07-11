import { useState, useCallback, useRef } from "react";
import type { UploadParams } from "@/types/compliance";
import type {
  NodeStatus,
  ComplianceResult,
} from "@/services/complianceApi";
import { API_BASE } from "@/services/complianceApi";

export interface UseComplianceCheckReturn {
  submit: (params: UploadParams & { projectId?: string }) => Promise<ComplianceResult>;
  isStreaming: boolean;
  nodeStatuses: NodeStatus[];
  currentNode: string | null;
  error: { message: string; retryable: boolean } | null;
  retry: () => void;
}

/**
 * Custom hook that uses SSE (Server-Sent Events) for compliance checks.
 *
 * Flow:
 * 1. POST multipart/form-data to /api/compliance/check
 * 2. Server responds with SSE stream (text/event-stream)
 * 3. Events: "initiated" → "node_status" (per node) → "result" | "error"
 * 4. Resolve the promise with the compliance result
 */
export function useComplianceCheck(): UseComplianceCheckReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [nodeStatuses, setNodeStatuses] = useState<NodeStatus[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [error, setError] = useState<{
    message: string;
    retryable: boolean;
  } | null>(null);

  const lastParamsRef = useRef<(UploadParams & { projectId?: string }) | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(
    async (params: UploadParams & { projectId?: string }): Promise<ComplianceResult> => {
      lastParamsRef.current = params;

      // Reset state
      setIsStreaming(true);
      setNodeStatuses([]);
      setCurrentNode(null);
      setError(null);

      // Abort previous request if any
      if (abortRef.current) {
        abortRef.current.abort();
      }
      abortRef.current = new AbortController();

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
      formData.append("platform", params.platform);
      if (params.projectId) {
        formData.append("project_id", params.projectId);
      }
      const username = (params as unknown as Record<string, unknown>).username as string | undefined;
      if (username) {
        formData.append("username", username);
      }

      console.log("[ComplianceCheck] Submitting compliance check (SSE)", {
        hasFile: !!params.file,
        hasText: !!params.text,
        market: params.market,
        projectId: params.projectId,
      });

      try {
        const res = await fetch(`${API_BASE}/api/compliance/check`, {
          method: "POST",
          body: formData,
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          const retryable = res.status >= 500;
          const message = res.status === 400
            ? "Validation error: please provide a file or text"
            : `Server error (${res.status})`;
          setError({ message, retryable });
          setIsStreaming(false);
          throw new Error(message);
        }

        // Parse SSE stream
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalResult: ComplianceResult | null = null;
        let taskId = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event = JSON.parse(jsonStr);

              switch (event.type) {
                case "initiated":
                  taskId = event.task_id;
                  console.log("[ComplianceCheck] Initiated:", event);
                  setNodeStatuses([{
                    type: "node_status",
                    node: "upload",
                    status: "completed",
                    description: "Media uploaded successfully",
                  }]);
                  setCurrentNode("upload");
                  break;

                case "node_status":
                  setNodeStatuses((prev) => {
                    const existing = prev.findIndex((s) => s.node === event.node);
                    const status: NodeStatus = {
                      type: "node_status",
                      node: event.node,
                      status: event.status,
                      description: event.description || event.node,
                    };
                    if (existing >= 0) {
                      const updated = [...prev];
                      updated[existing] = status;
                      return updated;
                    }
                    return [...prev, status];
                  });
                  if (event.status === "running") {
                    setCurrentNode(event.node);
                  }
                  break;

                case "result":
                  finalResult = {
                    ...event.data,
                    check_id: taskId || event.data.task_id,
                    market: event.data.market,
                  };
                  console.log("[ComplianceCheck] ✅ Result received:", finalResult);
                  break;

                case "error":
                  setError({ message: event.message, retryable: true });
                  setIsStreaming(false);
                  throw new Error(event.message);
              }
            } catch (parseErr) {
              // Skip malformed lines
              if (parseErr instanceof Error && parseErr.message !== jsonStr) {
                throw parseErr;
              }
            }
          }
        }

        setIsStreaming(false);

        if (finalResult) {
          return finalResult;
        }

        throw new Error("Stream ended without a result");

      } catch (err: unknown) {
        setIsStreaming(false);
        if (err instanceof DOMException && err.name === "AbortError") {
          throw err;
        }
        if (!(err instanceof Error && error)) {
          const message = err instanceof Error ? err.message : "Connection failed";
          setError({ message, retryable: true });
        }
        throw err;
      }
    },
    [error]
  );

  const retry = useCallback(() => {
    if (lastParamsRef.current) {
      submit(lastParamsRef.current);
    }
  }, [submit]);

  return { submit, isStreaming, nodeStatuses, currentNode, error, retry };
}
