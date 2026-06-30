/**
 * TaskDetailPage — routes to the correct detail view based on task type.
 *
 * - Compliance tasks: loads the task, extracts saved pipeline_state,
 *   then redirects to /compliance/:taskId passing restored result as location.state
 * - Generation tasks: renders the GenerationCanvas inline
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router";
import { getTask } from "@/services/taskApi";
import type { TaskDetail } from "@/services/taskApi";
import { GenerationCanvas } from "@/components/workspace/canvas/GenerationCanvas";
import { deserializePipeline } from "@/components/workspace/canvas/graphModel";

export default function TaskDetailPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTask = useCallback(async () => {
    if (!projectId || !taskId) return;
    setLoading(true);
    setError(null);

    try {
      const data = await getTask(projectId, taskId);

      console.log("[TaskDetail] Full task API response:", JSON.stringify(data, null, 2));

      if (data.type === "compliance") {
        // Extract saved workflow state from pipeline_state
        const ps = data.compliance.result_json as Record<string, unknown> | null;

        // Build the compliance result from stored data
        // pipeline_state contains compliance_step, compliance_result, compliance_status
        const anyTask = data as unknown as Record<string, unknown>;
        const pipelineState = anyTask.pipeline_state as Record<string, unknown> | undefined;
        const savedStep = (pipelineState?.compliance_step as string) ?? "review";
        const savedStatus = (pipelineState?.compliance_status as string) ?? "checked";

        // compliance_result in pipeline_state is the full result object
        const savedResult = pipelineState?.compliance_result as Record<string, unknown> | null
          // fallback: build from compliance join data
          ?? (ps ? {
            check_id: data.compliance.result_json?.check_id as string ?? taskId,
            market: data.compliance.market,
            ethnicity: (data.compliance as Record<string, unknown>).ethnicity,
            age_group: (data.compliance as Record<string, unknown>).age_group,
            platform: (data.compliance as Record<string, unknown>).platform,
            s3_upload_key: data.compliance.s3_upload_key,
            s3_segmented_key: data.compliance.s3_segmented_key,
            s3_remix_key: data.compliance.s3_remix_key,
            ...ps,
          } : null);

        // Always enrich with table-level metadata that may not be in result_json
        if (savedResult) {
          if (!savedResult.ethnicity) savedResult.ethnicity = (data.compliance as Record<string, unknown>).ethnicity;
          if (!savedResult.age_group) savedResult.age_group = (data.compliance as Record<string, unknown>).age_group;
          if (!savedResult.platform) savedResult.platform = (data.compliance as Record<string, unknown>).platform;
          if (!savedResult.market) savedResult.market = data.compliance.market;
          if (!savedResult.s3_upload_key) savedResult.s3_upload_key = data.compliance.s3_upload_key;
          if (!savedResult.s3_segmented_key) savedResult.s3_segmented_key = data.compliance.s3_segmented_key;
          if (!savedResult.s3_remix_key) savedResult.s3_remix_key = data.compliance.s3_remix_key;
        }

        console.log("[TaskDetail] Restoring compliance task", {
          taskId,
          savedStep,
          savedStatus,
          hasResult: !!savedResult,
        });

        // Redirect to compliance workspace with restored state
        navigate(`/dashboard/project/${projectId}/compliance/${taskId}`, {
          replace: true,
          state: {
            restoredTaskId: taskId,
            restoredStep: savedStep,
            restoredStatus: savedStatus,
            restoredResult: savedResult,
            restoredMediaType: data.compliance.media_type ?? "image",
          },
        });
        return;
      }

      setTask(data);
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        navigate("/not-found", {
          replace: true,
          state: { type: "not_found", message: "This task doesn't exist or has been deleted." },
        });
        return;
      }
      if (err instanceof Error && err.message.includes("403")) {
        navigate("/not-found", {
          replace: true,
          state: { type: "unauthorized", message: "This task belongs to another project. You don't have permission to view it." },
        });
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load task");
    } finally {
      setLoading(false);
    }
  }, [projectId, taskId, navigate]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading task...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-500">{error}</p>
        <button
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={fetchTask}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!task || !projectId || !taskId) return null;

  // Generation task — render inline
  const initialState = task.type === "generation" && task.pipeline_state
    ? deserializePipeline(task.pipeline_state)
    : undefined;

  return (
    <div className="h-full">
      <GenerationCanvas
        projectId={projectId}
        taskId={taskId}
        initialState={initialState}
      />
    </div>
  );
}
