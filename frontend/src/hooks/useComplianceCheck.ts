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
 * Derives the WebSocket base URL from the HTTP API_BASE.
 * Converts http:// → ws:// and https:// → wss://
 */
function getWsBase(): string {
  if (API_BASE.startsWith("https://")) {
    return API_BASE.replace("https://", "wss://");
  }
  return API_BASE.replace("http://", "ws://");
}

/**
 * Custom hook that encapsulates the WebSocket streaming logic for compliance checks.
 *
 * Flow:
 * 1. POST multipart/form-data to /api/compliance/check → get { check_id }
 * 2. Connect to WebSocket at /ws/{check_id}
 * 3. Listen for node_status, result, interrupt, and error events
 * 4. Resolve the promise when result arrives
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
  const wsRef = useRef<WebSocket | null>(null);

  const submit = useCallback(
    async (params: UploadParams & { projectId?: string }): Promise<ComplianceResult> => {
      // Store params for retry
      lastParamsRef.current = params;

      // Reset state
      setIsStreaming(true);
      setNodeStatuses([]);
      setCurrentNode(null);
      setError(null);

      // Close any previous WebSocket
      if (wsRef.current) {
        console.log("[ComplianceCheck] Closing previous WebSocket connection");
        wsRef.current.close();
        wsRef.current = null;
      }

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
      if (params.projectId) {
        formData.append("project_id", params.projectId);
      }
      // Pass username if available (for S3 bucket path)
      const username = (params as Record<string, unknown>).username as string | undefined;
      if (username) {
        formData.append("username", username);
      }

      console.log("[ComplianceCheck] Submitting compliance check", {
        hasFile: !!params.file,
        hasText: !!params.text,
        market: params.market,
        ethnicity: params.ethnicity,
        ageGroup: params.ageGroup,
        projectId: params.projectId,
        username,
      });

      try {
        // Step 1: POST to initiate the check — returns JSON with check_id
        console.log("[ComplianceCheck] POST /api/compliance/check");
        const res = await fetch(`${API_BASE}/api/compliance/check`, {
          method: "POST",
          body: formData,
        });

        console.log("[ComplianceCheck] Response status:", res.status);

        if (!res.ok) {
          const retryable = res.status >= 500;
          const message =
            res.status === 400
              ? "Validation error: please provide a file or text"
              : `Server error (${res.status})`;
          console.error("[ComplianceCheck] HTTP error:", message);
          setError({ message, retryable });
          setIsStreaming(false);
          throw new Error(message);
        }

        const initData = await res.json() as {
          check_id: string;
          media_type: string;
          status: string;
          ws_url: string;
          s3_upload_key: string | null;
        };

        console.log("[ComplianceCheck] Check initiated:", initData);

        // Store the upload URL for inclusion in final result
        const uploadUrl = initData.s3_upload_key;

        // Step 2: Connect to WebSocket for real-time streaming
        const wsBase = getWsBase();
        const wsUrl = `${wsBase}/ws/${initData.check_id}`;
        console.log("[ComplianceCheck] Connecting WebSocket:", wsUrl);

        return new Promise<ComplianceResult>((resolve, reject) => {
          const ws = new WebSocket(wsUrl);
          wsRef.current = ws;

          // Timeout — if no result after 5 minutes, give up
          const timeout = setTimeout(() => {
            console.warn("[ComplianceCheck] WebSocket timeout after 5 minutes");
            ws.close();
            const msg = "Pipeline timed out — no result received within 5 minutes";
            setError({ message: msg, retryable: true });
            setIsStreaming(false);
            reject(new Error(msg));
          }, 5 * 60 * 1000);

          ws.onopen = () => {
            console.log("[ComplianceCheck] WebSocket connected");
            // Send a ping to confirm connection
            ws.send(JSON.stringify({ action: "ping" }));
          };

          ws.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data) as Record<string, unknown>;
              const eventType = data.type as string;
              console.log("[ComplianceCheck] WS event:", eventType, data);

              switch (eventType) {
                case "node_status": {
                  const nodeStatus: NodeStatus = {
                    type: "node_status",
                    node: data.node as string,
                    status: data.status as "running" | "completed" | "error",
                    description: data.description as string,
                  };
                  setNodeStatuses((prev) => [...prev, nodeStatus]);
                  setCurrentNode(nodeStatus.node);
                  console.log("[ComplianceCheck] Node status:", nodeStatus.node, "→", nodeStatus.status);
                  break;
                }

                case "result": {
                  clearTimeout(timeout);
                  const payload = data.data as Record<string, unknown>;
                  const innerResult = (payload.result ?? payload) as Record<string, unknown>;
                  const result = {
                    check_id: initData.check_id,
                    market: (payload.market as string) || initData.media_type,
                    s3_upload_key: uploadUrl || (payload.s3_upload_key as string) || undefined,
                    s3_segmented_key: (payload.s3_segmented_key as string) || undefined,
                    ...innerResult,
                  } as ComplianceResult;
                  console.log("[ComplianceCheck] ✅ Result received:", result);
                  setIsStreaming(false);
                  ws.close();
                  resolve(result);
                  break;
                }

                case "media_urls": {
                  // Late-arriving media URLs — log but don't block
                  console.log("[ComplianceCheck] 🖼️ Media URLs received (late):", data);
                  break;
                }

                case "interrupt": {
                  console.log("[ComplianceCheck] ⏸ Interrupt received — auto-resuming with 'ok'");
                  // Human-in-the-loop: auto-approve for now (send "ok")
                  ws.send(JSON.stringify({ action: "resume", decision: "ok" }));
                  break;
                }

                case "error": {
                  clearTimeout(timeout);
                  const errorMsg = (data.message as string) || "Pipeline error";
                  console.error("[ComplianceCheck] ❌ Error event:", errorMsg, data);
                  setError({ message: errorMsg, retryable: true });
                  setIsStreaming(false);
                  ws.close();
                  reject(new Error(errorMsg));
                  break;
                }

                case "pong":
                  console.log("[ComplianceCheck] Pong received — connection confirmed");
                  break;

                case "progress": {
                  const progressMsg = data.message as string;
                  console.log("[ComplianceCheck] 📌 Progress:", progressMsg);
                  // Emit as a node_status-like event so the CheckStep shows it
                  const progressStatus: NodeStatus = {
                    type: "node_status",
                    node: "progress",
                    status: "running" as "running" | "completed" | "error",
                    description: progressMsg,
                  };
                  setNodeStatuses((prev) => [...prev, progressStatus]);
                  break;
                }

                default:
                  console.log("[ComplianceCheck] Unknown event type:", eventType, data);
              }
            } catch (parseErr) {
              console.warn("[ComplianceCheck] Failed to parse WS message:", event.data, parseErr);
            }
          };

          ws.onerror = (err) => {
            clearTimeout(timeout);
            console.error("[ComplianceCheck] WebSocket error:", err);
            const msg = "WebSocket connection error";
            setError({ message: msg, retryable: true });
            setIsStreaming(false);
            reject(new Error(msg));
          };

          ws.onclose = (event) => {
            clearTimeout(timeout);
            console.log("[ComplianceCheck] WebSocket closed:", {
              code: event.code,
              reason: event.reason,
              wasClean: event.wasClean,
            });
            // Only set error if we didn't already resolve/reject
            if (isStreaming) {
              if (!event.wasClean) {
                setError({
                  message: "Connection lost unexpectedly",
                  retryable: true,
                });
                setIsStreaming(false);
              }
            }
          };
        });
      } catch (err: unknown) {
        setIsStreaming(false);
        console.error("[ComplianceCheck] Submit error:", err);
        if (!(err instanceof Error && error)) {
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
    console.log("[ComplianceCheck] Retrying with previous params");
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
