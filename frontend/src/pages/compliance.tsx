import { useReducer, useRef, useCallback, useEffect, useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router";
import { useComplianceCheck } from "@/hooks/useComplianceCheck";
import { useComplianceRemix } from "@/hooks/useComplianceRemix";
import { useAuth } from "@/hooks/useAuth";
import { projectReducer, initialProjectStore } from "@/reducers/projectReducer";
import { StepNavigator } from "@/components/compliance/StepNavigator";
import { UploadStep } from "@/components/compliance/UploadStep";
import { CheckStep } from "@/components/compliance/CheckStep";
import { ReviewStep } from "@/components/compliance/ReviewStep";
import { RemixStep } from "@/components/compliance/RemixStep";
import { ComparisonView } from "@/components/compliance/ComparisonView";
import type { UploadParams, Project } from "@/types/compliance";
import { WORKFLOW_STEPS } from "@/types/compliance";
import type { ComplianceResult } from "@/services/complianceApi";
import { API_BASE } from "@/services/complianceApi";
import { savePipeline } from "@/services/taskApi";


/**
 * Derives media type from UploadParams (file MIME type or defaults to "text").
 */
function deriveMediaType(params: UploadParams): Project["mediaType"] {
  if (!params.file) return "text";
  if (params.file.type.startsWith("video/")) return "video";
  if (params.file.type.startsWith("image/")) return "image";
  if (params.file.type.startsWith("audio/")) return "audio";
  return "text";
}

/**
 * Generates a unique project ID.
 */
function generateId(): string {
  return crypto.randomUUID?.() ?? `proj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * ComplianceWorkspace — the top-level orchestrator for the project-based
 * compliance workflow. Replaces the old queue-based layout with a step-driven
 * flow: Upload → Check → Review → Remix → Compare.
 *
 * Requirements: 1.1, 1.2, 1.3, 2.5, 2.6, 3.2, 4.5, 6.3, 8.1, 9.2, 9.4,
 *              11.1, 11.2, 11.3, 12.3, 12.5
 */
export default function DashboardCompliance() {
  const { projectId: routeProjectId, taskId: routeTaskId } = useParams<{ projectId: string; taskId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(projectReducer, initialProjectStore);
  const { user } = useAuth();
  const complianceCheck = useComplianceCheck();
  const remix = useComplianceRemix();

  // Read restored task state passed from task-detail.tsx navigation
  const restoredState = location.state as {
    restoredTaskId?: string;
    restoredStep?: string;
    restoredResult?: ComplianceResult;
    restoredMediaType?: string;
  } | null;

  // Task history for this project (fetched from API)
  const [taskHistory, setTaskHistory] = useState<{ id: string; reference_id: string | null; type: string; status: string; summary: string; created_at: string }[]>([]);

  // Track the current task ID for step state persistence
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  // Track whether we've already attempted direct URL task load
  const directLoadAttempted = useRef(false);

  // Restore task state when navigated from task-detail.tsx
  useEffect(() => {
    // A task URL is reloadable/shareable. Let the direct API restore below be
    // authoritative rather than relying on transient React navigation state.
    if (routeTaskId) return;
    if (!restoredState?.restoredResult || !restoredState.restoredTaskId) return;

    const { restoredTaskId, restoredStep, restoredResult, restoredMediaType } = restoredState;
    const id = routeProjectId ?? restoredTaskId;

    // Build a project from the restored state
    const restoredProject: Project = {
      id,
      campaignName: restoredResult.check_id ?? restoredTaskId,
      mediaType: (restoredMediaType ?? "image") as Project["mediaType"],
      currentStep: (restoredStep as Project["currentStep"]) ?? "review",
      completedSteps: ["upload", "check", "review"],
      uploadParams: { market: restoredResult.market ?? "malaysia", ethnicity: "malay", ageGroup: "all_ages", platform: "general" },
      result: restoredResult,
      remixResult: null,
      error: null,
      createdAt: Date.now(),
    };

    dispatch({ type: "CREATE_PROJECT", payload: restoredProject });
    setCurrentTaskId(restoredTaskId);
    directLoadAttempted.current = true;
  }, []); // run once on mount

  // Direct URL access: if we have a routeTaskId but no restored state,
  // fetch the task directly from the API and restore it
  useEffect(() => {
    if (directLoadAttempted.current) return;
    if (!routeProjectId || !routeTaskId) return;
    directLoadAttempted.current = true;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/projects/${routeProjectId}/tasks/${routeTaskId}`);
        if (!res.ok) return;
        const task = await res.json();

        console.log("[Compliance] Task detail full JSON:", JSON.stringify(task, null, 2));

        if (task.type !== "compliance") return;

        const pipelineState = task.pipeline_state as Record<string, unknown> | undefined;
        const savedStep = (pipelineState?.compliance_step as string) ?? "review";
        const compliance = task.compliance as Record<string, unknown> | undefined;
        const resultJson = compliance?.result_json as Record<string, unknown> | null;

        // Build the compliance result from stored data
        const savedResult = (pipelineState?.compliance_result as Record<string, unknown> | null)
          ?? (resultJson ? {
            check_id: (resultJson.check_id as string) ?? routeTaskId,
            market: compliance?.market,
            ethnicity: compliance?.ethnicity,
            age_group: compliance?.age_group,
            platform: compliance?.platform,
            s3_upload_key: compliance?.s3_upload_key,
            s3_segmented_key: compliance?.s3_segmented_key,
            s3_remix_key: compliance?.s3_remix_key,
            ...resultJson,
          } : null);

        // Always enrich with table-level metadata that may not be in result_json/pipeline_state
        if (savedResult) {
          if (!savedResult.ethnicity) savedResult.ethnicity = compliance?.ethnicity;
          if (!savedResult.age_group) savedResult.age_group = compliance?.age_group;
          if (!savedResult.platform) savedResult.platform = compliance?.platform;
          if (!savedResult.market) savedResult.market = compliance?.market;
          if (!savedResult.s3_upload_key) savedResult.s3_upload_key = compliance?.s3_upload_key;
          if (!savedResult.s3_segmented_key) savedResult.s3_segmented_key = compliance?.s3_segmented_key;
          if (!savedResult.s3_remix_key) savedResult.s3_remix_key = compliance?.s3_remix_key;
        }

        if (!savedResult) return;

        const mediaType = (compliance?.media_type as string) ?? "image";
        const persistedRemix = resultJson?.remix as Record<string, unknown> | undefined;
        // A video is eligible for Compare only after an actual Omni edit. This
        // prevents historical redact/mute fallback assets from being presented
        // as a completed AI remediation.
        const hasConfirmedRemix = compliance?.status === "remediated"
          && !!compliance?.s3_remix_key
          && (mediaType !== "video" || persistedRemix?.omni_edit_status === "completed");
        const restoredStep = hasConfirmedRemix ? "compare" : savedStep;
        const restoredRemix = pipelineState?.compliance_remix
          ?? persistedRemix
          ?? (hasConfirmedRemix ? {
            type: "remix",
            s3_remix_url: compliance?.s3_remix_key,
          } : null);

        // Determine which steps have been completed based on saved state
        const completedSteps: Project["completedSteps"] = ["upload", "check", "review"];
        if (restoredStep === "remix" || restoredStep === "compare") {
          completedSteps.push("remix");
        }
        if (restoredStep === "compare") {
          completedSteps.push("compare");
        }

        const restoredProject: Project = {
          id: routeProjectId,
          campaignName: (savedResult.check_id as string) ?? routeTaskId,
          mediaType: mediaType as Project["mediaType"],
          currentStep: (restoredStep as Project["currentStep"]) ?? "review",
          completedSteps,
          uploadParams: { market: (savedResult.market as string) ?? "malaysia", ethnicity: "malay", ageGroup: "all_ages", platform: "general" },
          result: savedResult as unknown as ComplianceResult,
          remixResult: restoredRemix,
          error: null,
          createdAt: Date.now(),
        };

        dispatch({ type: "CREATE_PROJECT", payload: restoredProject });
        setCurrentTaskId(routeTaskId);
      } catch {
        // Non-fatal — user will see the upload step
      }
    })();
  }, [routeProjectId, routeTaskId, restoredState]);

  // Fetch task history on mount for project-scoped routes
  useEffect(() => {
    if (!routeProjectId) return;
    fetch(`${API_BASE}/api/projects/${routeProjectId}/tasks`)
      .then((res) => res.ok ? res.json() : [])
      .then((data: { id: string; reference_id: string | null; type: string; status: string; summary: string; created_at: string }[]) => {
        // Only show compliance tasks in the sidebar
        setTaskHistory(data.filter((t) => t.type === "compliance"));
      })
      .catch(() => setTaskHistory([]));
  }, [routeProjectId]);

  // Persist workflow step state to Supabase tasks.pipeline_state
  const persistStepState = useCallback(async (
    taskId: string,
    step: string,
    result: ComplianceResult | null,
    status: string = "checked",
    remixResult: unknown = null
  ) => {
    if (!routeProjectId || !taskId) return;
    try {
      // Strip heavy fields (bounding boxes) before persisting — already on segmented image
      let trimmedResult = result;
      if (result) {
        const { segmentation, ...rest } = result as unknown as Record<string, unknown>;
        const seg = segmentation as Record<string, unknown> | undefined;
        trimmedResult = {
          ...rest,
          segmentation: seg ? { num_masks: seg.num_masks, segmented_image_path: seg.segmented_image_path } : undefined,
        } as ComplianceResult;
      }

      await savePipeline(routeProjectId, taskId, {
        nodes: [],
        edges: [],
        viewport: { panX: 0, panY: 0, zoom: 1 },
        // @ts-ignore — extending PipelineState for compliance use
        compliance_step: step,
        compliance_result: trimmedResult,
        compliance_remix: remixResult,
        compliance_status: status,
      });
    } catch {
      // Non-fatal
    }
  }, [routeProjectId]);

  // "New Check" resets to upload step — clear active project so the upload form shows
  const handleNewCheck = useCallback(() => {
    setCurrentTaskId(null);
    // Clear the active project entirely so renderStepContent() shows the default Upload form
    dispatch({ type: "SET_ACTIVE_PROJECT", projectId: "" });
  }, []);

  // Derive active project from state (empty string means "no active project")
  const activeProject: Project | null = state.activeProjectId
    ? state.projects.get(state.activeProjectId) ?? null
    : null;

  // ─── Submit flow ────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (params: UploadParams) => {
      console.log("[Compliance] handleSubmit called — NEW CHECK STARTING", {
        hasFile: !!params.file,
        fileName: params.file?.name,
        hasText: !!params.text,
        market: params.market,
        ethnicity: params.ethnicity,
      });

      const id = routeProjectId || generateId();
      const newProject: Project = {
        id,
        campaignName: params.file?.name?.replace(/\.[^/.]+$/, "") ?? "Text Ad",
        mediaType: deriveMediaType(params),
        currentStep: "check",
        completedSteps: [],
        uploadParams: params,
        result: null,
        remixResult: null,
        error: null,
        createdAt: Date.now(),
      };

      dispatch({ type: "CREATE_PROJECT", payload: newProject });

      try {
        console.log("[Compliance] Calling complianceCheck.submit...");
        const result: ComplianceResult = await complianceCheck.submit({
          ...params,
          projectId: id,
          username: user?.profile?.email ?? "anonymous",
        } as UploadParams & { projectId: string });

        console.log("[Compliance] Check complete, result:", result);

        // Enrich result with metadata from upload params in case backend drops them
        result.ethnicity = result.ethnicity || params.ethnicity;
        result.age_group = result.age_group || params.ageGroup;
        result.platform = result.platform || params.platform;
        result.market = result.market || params.market;

        dispatch({ type: "SET_RESULT", projectId: id, result });

        // Persist step state — find the task that was just created
        if (routeProjectId) {
          try {
            const tasksRes = await fetch(`${API_BASE}/api/projects/${routeProjectId}/tasks`);
            if (tasksRes.ok) {
              const tasks = await tasksRes.json();
              const latestTask = tasks[0]; // ordered by created_at desc
              if (latestTask?.id) {
                setCurrentTaskId(latestTask.id);
                // Update URL to include the task ID
                window.history.replaceState(null, "", `/dashboard/project/${routeProjectId}/compliance/${latestTask.id}`);
                await persistStepState(latestTask.id, "review", result, "reviewed");
              }
            }
          } catch {
            // Non-fatal
          }
        }
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          projectId: id,
          error: {
            step: "check",
            message: (err as Error).message || "Compliance check failed",
            retryable: true,
          },
        });
      }
    },
    [complianceCheck, routeProjectId, user, persistStepState]
  );

  // ─── Remix flow ─────────────────────────────────────────────────────────────
  const handleStartRemix = useCallback(async () => {
    if (!activeProject?.result) return;

    dispatch({
      type: "ADVANCE_STEP",
      projectId: activeProject.id,
      to: "remix",
    });

    try {
      const remixResult = await remix.startRemix(activeProject.result.check_id);
      if (!remixResult) {
        throw new Error("Remix completed without a generated remediation asset.");
      }
      dispatch({
        type: "SET_REMIX_RESULT",
        projectId: activeProject.id,
        remixResult,
      });
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        projectId: activeProject.id,
        error: {
          step: "remix",
          message: (err as Error).message || "Remix failed",
          retryable: true,
        },
      });
    }
  }, [activeProject, remix]);

  // ─── Retry flow ─────────────────────────────────────────────────────────────
  const handleRetry = useCallback(() => {
    if (!activeProject?.error) return;

    dispatch({ type: "CLEAR_ERROR", projectId: activeProject.id });

    if (activeProject.error.step === "check") {
      handleSubmit(activeProject.uploadParams);
    } else if (activeProject.error.step === "remix") {
      handleStartRemix();
    }
  }, [activeProject, handleSubmit, handleStartRemix]);

  // ─── Step content rendering ─────────────────────────────────────────────────
  function renderStepContent() {
    if (!activeProject) {
      return (
        <UploadStep
          onSubmit={handleSubmit}
          isSubmitting={complianceCheck.isStreaming}
          error={null}
          onRetry={handleRetry}
        />
      );
    }

    switch (activeProject.currentStep) {
      case "upload":
        return (
          <UploadStep
            onSubmit={handleSubmit}
            isSubmitting={complianceCheck.isStreaming}
            error={
              activeProject.error
                ? {
                    message: activeProject.error.message,
                    retryable: activeProject.error.retryable,
                  }
                : null
            }
            onRetry={handleRetry}
          />
        );

      case "check":
        return (
          <CheckStep
            nodeStatuses={complianceCheck.nodeStatuses}
            currentNode={complianceCheck.currentNode}
            isStreaming={complianceCheck.isStreaming}
            mediaType={activeProject.mediaType}
            error={
              activeProject.error
                ? {
                    message: activeProject.error.message,
                    retryable: activeProject.error.retryable,
                  }
                : null
            }
            onRetry={handleRetry}
          />
        );

      case "review":
        return activeProject.result ? (
          <ReviewStep
            result={activeProject.result}
            onStartRemix={handleStartRemix}
            isRemixAvailable={activeProject.mediaType === "image" || activeProject.mediaType === "audio" || activeProject.mediaType === "video"}
            mediaType={activeProject.mediaType}
          />
        ) : null;

      case "remix":
        return (
          <RemixStep
            remixNodes={remix.remixNodes}
            currentNode={remix.currentNode}
            isRemixing={remix.isRemixing}
            remixComplete={remix.remixComplete}
            remixError={remix.remixError ?? activeProject.error?.message ?? null}
            remixOutcome={remix.remixOutcome}
            cannotFixData={remix.cannotFixData}
            imageEditResult={remix.imageEditResult}
            editFailedData={remix.editFailedData}
            onRetry={handleRetry}
            mediaType={activeProject.mediaType}
          />
        );

      case "compare":
        return activeProject.result ? (
          <ComparisonView
            originalResult={activeProject.result}
            remixResult={activeProject.remixResult}
            mediaType={activeProject.mediaType}
            onRegenerate={handleStartRemix}
          />
        ) : null;
    }
  }

  // ─── Layout ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full gap-4">
      {/* Left panel — sidebar with task history + new check button */}
      <div className="w-64 shrink-0 flex flex-col gap-2">
        {/* All Tasks + New Check buttons */}
        {routeProjectId && (
          <>
            <button
              onClick={() => navigate(`/dashboard/project/${routeProjectId}`)}
              className="mx-2 mt-2 flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-text-muted hover:text-accent-blue transition-colors"
            >
              ← All Tasks
            </button>
            <button
              onClick={handleNewCheck}
              className="mx-2 flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-outline-variant px-3 py-2 text-xs font-semibold text-text-muted hover:border-accent-blue hover:text-accent-blue transition-colors"
            >
              + New Check
            </button>
          </>
        )}

        {/* Task history from API */}
        {taskHistory.length > 0 && (
          <div className="px-2 py-1">
            <p className="text-[10px] font-bold uppercase text-text-muted tracking-wider mb-1.5">Previous Checks</p>
            <div className="space-y-1 max-h-[300px] overflow-y-auto">
              {taskHistory.map((task) => {
                // Highlight active if this task matches the current one
                const isActive = currentTaskId === task.id;

                return (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => {
                      if (routeProjectId) {
                        // Navigate to task-detail which will redirect back with restored state
                        navigate(`/dashboard/project/${routeProjectId}/${task.id}`);
                      }
                    }}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs w-full text-left transition-colors ${
                      isActive
                        ? "bg-accent-blue/10 text-accent-blue border border-accent-blue/20"
                        : "text-text-muted bg-surface-inset/50 hover:bg-surface-inset hover:text-text-body cursor-pointer"
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full shrink-0 ${
                      task.status === "remediated" || task.status === "remix_failed" ? "bg-red-500" :
                      task.status === "checked" ? "bg-amber-500" : "bg-emerald-500"
                    }`} />
                    <span className="truncate flex-1">{task.summary || `${task.type} • ${task.status}`}</span>
                    <span className="text-[10px] shrink-0">{new Date(task.created_at).toLocaleDateString()}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col gap-4 px-4">
        {/* Step Navigator — visible when a project is active */}
        {activeProject && (
          <div className="flex justify-center pt-2">
            <StepNavigator
              steps={WORKFLOW_STEPS}
              currentStep={activeProject.currentStep}
              completedSteps={activeProject.completedSteps}
              disabledSteps={
                // For restored historical checks, disable upload/check tabs
                // since those steps are already finished and have no live data
                currentTaskId ? ["upload", "check"] : []
              }
              onStepClick={(step) =>
                dispatch({
                  type: "NAVIGATE_TO_STEP",
                  projectId: activeProject.id,
                  step,
                })
              }
            />
          </div>
        )}

        {/* Main content area */}
        <div className="step-content flex-1">{renderStepContent()}</div>
      </div>
    </div>
  );
}
