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

interface ProgressStep {
  step_name: string;
  status: "running" | "completed" | "error";
  message: string | null;
  created_at: string;
}

interface ProgressResponse {
  steps: ProgressStep[];
  is_terminal: boolean;
}

/**
 * Custom hook that uses REST API polling for compliance checks.
 *
 * Flow:
 * 1. POST multipart/form-data to /api/compliance/check → get { check_id }
 * 2. Poll GET /api/compliance/{check_id}/progress every 2 seconds
 * 3. Update nodeStatuses from progress steps
 * 4. When is_terminal=true, fetch GET /api/compliance/{check_id} for full result
 * 5. Resolve the promise with the compliance result
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
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const submit = useCallback(
    async (params: UploadParams & { projectId?: string }): Promise<ComplianceResult> => {
      lastParamsRef.current = params;

      // Reset state
      setIsStreaming(true);
      setNodeStatuses([]);
      setCurrentNode(null);
      setError(null);
      stopPolling();

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

      console.log("[ComplianceCheck] Submitting compliance check", {
        hasFile: !!params.file,
        hasText: !!params.text,
        market: params.market,
        projectId: params.projectId,
      });

      try {
        // Step 1: POST to initiate the check
        const res = await fetch(`${API_BASE}/api/compliance/check`, {
          method: "POST",
          body: formData,
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

        const initData = await res.json() as {
          check_id: string;
          media_type: string;
          status: string;
          s3_upload_key: string | null;
        };

        console.log("[ComplianceCheck] Check initiated:", initData);
        const uploadUrl = initData.s3_upload_key;

        // Step 2: Poll for progress
        return new Promise<ComplianceResult>((resolve, reject) => {
          const checkId = initData.check_id;

          // Timeout after 5 minutes
          const timeout = setTimeout(() => {
            stopPolling();
            const msg = "Pipeline timed out — no result within 5 minutes";
            setError({ message: msg, retryable: true });
            setIsStreaming(false);
            reject(new Error(msg));
          }, 5 * 60 * 1000);

          // Set initial "processing" status
          setNodeStatuses([{
            type: "node_status",
            node: "pipeline",
            status: "running",
            description: "Compliance check in progress...",
          }]);
          setCurrentNode("pipeline");

          pollingRef.current = setInterval(async () => {
            try {
              const progressRes = await fetch(`${API_BASE}/api/compliance/${checkId}/progress`);
              if (!progressRes.ok) return;

              const progress: ProgressResponse = await progressRes.json();

              // Update node statuses from progress steps
              const statuses: NodeStatus[] = progress.steps.map((step) => ({
                type: "node_status" as const,
                node: step.step_name,
                status: step.status,
                description: step.message || step.step_name,
              }));
              setNodeStatuses(statuses);

              // Set current node to the latest running step
              const runningStep = progress.steps.filter(s => s.status === "running").pop();
              const lastStep = progress.steps[progress.steps.length - 1];
              setCurrentNode(runningStep?.step_name || lastStep?.step_name || null);

              // If terminal, fetch the full result
              if (progress.is_terminal) {
                stopPolling();
                clearTimeout(timeout);

                // Check if any step errored
                const errorStep = progress.steps.find(s => s.status === "error");
                if (errorStep) {
                  const msg = errorStep.message || "Pipeline failed";
                  setError({ message: msg, retryable: true });
                  setIsStreaming(false);
                  reject(new Error(msg));
                  return;
                }

                // Fetch full result
                const resultRes = await fetch(`${API_BASE}/api/compliance/${checkId}`);
                if (!resultRes.ok) {
                  const msg = "Failed to fetch compliance result";
                  setError({ message: msg, retryable: true });
                  setIsStreaming(false);
                  reject(new Error(msg));
                  return;
                }

                const resultData = await resultRes.json();
                const result: ComplianceResult = {
                  ...resultData,
                  check_id: checkId,
                  market: resultData.market || params.market,
                  s3_upload_key: resultData.s3_upload_key || uploadUrl || undefined,
                };

                console.log("[ComplianceCheck] ✅ Result received:", result);
                setIsStreaming(false);
                resolve(result);
              }
            } catch (pollErr) {
              // Non-fatal polling error — just retry next interval
              console.warn("[ComplianceCheck] Poll error:", pollErr);
            }
          }, 5000);
        });

      } catch (err: unknown) {
        setIsStreaming(false);
        stopPolling();
        if (!(err instanceof Error && error)) {
          const message = err instanceof Error ? err.message : "Connection failed";
          setError({ message, retryable: true });
        }
        throw err;
      }
    },
    [stopPolling]
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
