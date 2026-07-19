/**
 * TaskDetailPage — routes to the correct detail view based on task type.
 *
 * - Compliance tasks: loads the task, extracts saved pipeline_state,
 *   then redirects to /compliance/:taskId passing restored result as location.state
 * - Generation tasks: renders the GenerationCanvas inline
 * - Guided mode: auto-triggers generation on mount when navigated from guided form
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { getTask } from "@/services/taskApi";
import type { TaskDetail } from "@/services/taskApi";
import { GenerationCanvas } from "@/components/workspace/canvas/GenerationCanvas";
import { deserializePipeline } from "@/components/workspace/canvas/graphModel";
import { streamGuidedGeneration } from "@/services/generationApi";
import type { PipelineState } from "@/components/workspace/canvas/graphModel";

export default function TaskDetailPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Guided mode state from navigation (set when user submits the guided form)
  const guidedState = location.state as {
    guidedMode?: boolean;
    designType?: string;
    guidedInputs?: Record<string, string>;
    guidedReferences?: string[];
  } | null;

  const [isGuidedMode] = useState(guidedState?.guidedMode === true);
  const [guidedRunning, setGuidedRunning] = useState(false);
  const guidedTriggered = useRef(false);

  // Pipeline state updated by guided generation stream
  const [guidedPipelineState, setGuidedPipelineState] = useState<PipelineState | undefined>(undefined);

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

      // Generic task links always open the task's Easy results surface. The
      // Advanced canvas remains an explicit opt-in from that results page.
      const isCanonicalModeRoute = location.pathname.includes("/easy/") || location.pathname.includes("/advance/") || location.pathname.includes("/advanced/");
      if (!isCanonicalModeRoute) {
        navigate(`/dashboard/project/${projectId}/easy/${taskId}/results`, { replace: true });
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
  }, [projectId, taskId, navigate, location.pathname]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  // Auto-trigger guided generation on mount when navigated from the guided form
  useEffect(() => {
    if (
      !guidedTriggered.current &&
      guidedState?.guidedMode &&
      guidedState.designType &&
      guidedState.guidedInputs &&
      projectId &&
      taskId &&
      task
    ) {
      guidedTriggered.current = true;
      setGuidedRunning(true);

      // Clear navigation state to prevent re-triggering on refresh
      window.history.replaceState({}, document.title);

      (async () => {
        try {
          for await (const event of streamGuidedGeneration(
            projectId,
            taskId,
            guidedState.designType!,
            guidedState.guidedInputs!,
            guidedState.guidedReferences ?? []
          )) {
            if (event.pipeline_state) {
              setGuidedPipelineState(event.pipeline_state);
            }
            if (event.error) {
              toast.error(`Generation error: ${event.error}`);
            }
          }
          toast.success("Ad generation completed!");
        } catch (err) {
          const message = err instanceof Error ? err.message : "Generation failed";
          toast.error(message);
        } finally {
          setGuidedRunning(false);
        }
      })();
    }
  }, [guidedState, projectId, taskId, task]);

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

  // Use guided pipeline state if available (updated from auto-trigger stream)
  const effectiveInitialState = guidedPipelineState ?? initialState;

  return (
    <div className="relative h-full">
      {/* Back to form link — shown when this task was triggered via guided mode */}
      {isGuidedMode && (
        <div className="absolute left-4 top-4 z-10">
          <button
            onClick={() => navigate(`/dashboard/project/${projectId}/easy`)}
            className="flex items-center gap-1.5 rounded-md border border-border bg-background/80 px-3 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur-sm transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            New Generation
          </button>
        </div>
      )}

      {/* Guided mode running indicator */}
      {guidedRunning && (
        <div className="absolute left-1/2 top-4 z-10 -translate-x-1/2">
          <div className="flex items-center gap-2 rounded-full border border-border bg-background/90 px-4 py-2 text-sm text-muted-foreground shadow-sm backdrop-blur-sm">
            <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
            Generating from guided form...
          </div>
        </div>
      )}

      <GenerationCanvas
        projectId={projectId}
        taskId={taskId}
        initialState={effectiveInitialState}
      />
    </div>
  );
}
